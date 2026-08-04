#!/usr/bin/env python3
"""route_eval — consistency tests for the Cortex routing protocol.

WHAT THIS MEASURES
    Whether the routing protocol still produces the behaviour cortex.md specifies.
    It answers "did something break?", not "was that a good route?".

WHAT IT DOES NOT MEASURE
    Routing quality. There is no oracle for that here, and the `canary` cases are
    explicitly recall checks: their answers are written in cortex.md, which the model
    can see. They detect document corruption or a protocol that stopped loading. They
    prove nothing about generalisation. The `rule`, `paired` and `shape` cases are the
    ones that test behaviour the document does not spell out for that exact task.

METHOD
    Each case spawns an isolated headless `claude -p` session so cases cannot influence
    each other. That isolation is the point: batching cases into one session would let
    an earlier answer anchor a later one, which destroys the paired comparisons.

    CORTEX_HOME is redirected to a throwaway sandbox for every run so that a model
    following the protocol (or a SessionStart hook) cannot append test routes to the
    real cortex log.

    The model is pinned and recorded. Results are only comparable across runs that used
    the same model, because routing behaviour is a property of model plus document, not
    the document alone. Holding the model fixed is what makes this a test of cortex.md.

    The routing line is parsed with `parse_route` imported from bin/cortex, so there is
    exactly one route grammar in the system. A second parser here would be free to drift
    from the real one, which is the class of bug this whole suite exists to catch.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORTEX_BIN = REPO / "bin" / "cortex"
CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")

TIERS = ["L1", "L2", "L3", "L4"]

# Reuse the real parser rather than reimplementing the grammar.
parse_route = SourceFileLoader("cortex_cli", str(CORTEX_BIN)).load_module().parse_route

PROMPT = """Route only. Do not perform the task. Do not use any tools, do not run any \
commands, and do not log anything anywhere.

Apply the Cortex routing protocol and output ONLY the single routing line, in the form
'System > Pattern [> Agent] @ L<n>' with optional [tags]. No explanation, no preamble,
no trailing commentary.

TASK: {task}"""


def sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def extract_route(text):
    """Return the first parseable routing line, tolerating stray commentary."""
    for line in (text or "").splitlines():
        line = line.strip().strip("`").strip()
        if not line:
            continue
        try:
            return parse_route(line), line
        except ValueError:
            continue
    return None, (text or "").strip()[:200]


def is_refusal(parsed):
    """A declined task is not a routing decision.

    The model may decline rather than route (e.g. a destructive request with no
    authorisation context). It still emits a well-formed line, so it parses, and the
    tier on that line is an artifact of the refusal rather than a calibration result.
    Scoring it as a tier failure would manufacture false protocol violations, so these
    are reported as their own outcome instead.
    """
    blob = f"{parsed.get('pattern') or ''} {parsed.get('agent') or ''}".lower()
    return any(w in blob for w in ("refuse", "refusal", "decline", "n/a"))


def is_fanout(parsed, raw):
    """Fan-out is declared either by the parallel marker or by the /team pattern."""
    blob = f"{parsed.get('agent') or ''} {parsed.get('pattern') or ''} {raw}"
    return "∥" in blob or "team" in (parsed.get("pattern") or "").lower()


def run_case(case, model, sandbox, claude_bin):
    env = dict(os.environ, CORTEX_HOME=str(sandbox))
    cmd = [claude_bin, "-p", PROMPT.format(task=case["task"]),
           "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--model", model]
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        payload = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "cost_usd": 0.0}
    except (json.JSONDecodeError, ValueError):
        return {"error": f"unparseable CLI output: {proc.stdout[:200]}", "cost_usd": 0.0}

    parsed, raw = extract_route(payload.get("result", ""))
    return {
        "raw": raw,
        "route": parsed,
        "cost_usd": payload.get("total_cost_usd") or 0.0,
        "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "error": None if parsed else "no parseable routing line",
    }


def check(assertion, case_id, results):
    """Evaluate one assertion. Returns (outcome, detail) where outcome is
    'pass' | 'fail' | 'refused'."""
    r = results[case_id]["modal"]
    if not r:
        return "fail", "no route produced"
    if results[case_id].get("indeterminate"):
        sigs = [f"{x['route']['system']}>{x['route']['pattern']}@{x['route']['tier']}"
                for x in results[case_id]["runs"] if x.get("route")]
        return "unstable", f"no majority across repeats: {sorted(set(sigs))}"
    if is_refusal(r):
        return "refused", f"model declined the task: {results[case_id]['raw'][:70]}"
    for dep in ("base",):
        if dep in assertion:
            base_r = results.get(assertion[dep], {}).get("modal")
            if base_r and is_refusal(base_r):
                return "refused", f"base case {assertion[dep]} was declined"
    ok, detail = _eval_assertion(assertion, case_id, results, r)
    return ("pass" if ok else "fail"), detail


def _eval_assertion(assertion, case_id, results, r):
    """Evaluate one assertion against a route that is known not to be a refusal."""
    kind, tier = assertion["type"], r["tier"]

    if kind == "tier_equals":
        return tier == assertion["value"], f"tier={tier} expected={assertion['value']}"
    if kind == "tier_max":
        ok = TIERS.index(tier) <= TIERS.index(assertion["value"])
        return ok, f"tier={tier} max={assertion['value']}"
    if kind in ("tier_gt", "tier_offset"):
        base = results.get(assertion["base"], {}).get("modal")
        if not base:
            return False, f"base case {assertion['base']} produced no route"
        delta = TIERS.index(tier) - TIERS.index(base["tier"])
        if kind == "tier_gt":
            return delta > 0, f"{base['tier']} -> {tier} (delta {delta:+d}, need >0)"
        return delta == assertion["offset"], \
            f"{base['tier']} -> {tier} (delta {delta:+d}, need {assertion['offset']:+d})"
    if kind == "fanout":
        actual = is_fanout(r, results[case_id]["raw"])
        return actual == assertion["value"], f"fanout={actual} expected={assertion['value']}"
    if kind == "pattern_contains":
        ok = assertion["value"].lower() in (r["pattern"] or "").lower()
        return ok, f"pattern={r['pattern']!r} contains={assertion['value']!r}"
    if kind == "system_equals":
        return r["system"] == assertion["value"], f"system={r['system']} expected={assertion['value']}"
    return False, f"unknown assertion type {kind!r}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="sonnet", help="model to pin (default: sonnet)")
    ap.add_argument("--cases", default=str(Path(__file__).parent / "cases.json"))
    ap.add_argument("--only", action="append", help="run only these case ids (repeatable)")
    ap.add_argument("--kind", action="append", help="run only these kinds (canary/rule/paired/shape)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per case. Repeats estimate stability; they do NOT increase "
                         "sample size, the statistical unit stays the case (default: 1)")
    ap.add_argument("--jobs", type=int, default=4, help="parallel sessions (default: 4)")
    ap.add_argument("--out", default=None, help="results JSON (default: <state>/eval/run-<ts>.json)")
    ap.add_argument("--dry-run", action="store_true", help="list what would run, spend nothing")
    args = ap.parse_args()

    claude_bin = shutil.which("claude")
    if not claude_bin and not args.dry_run:
        print("error: `claude` not found on PATH", file=sys.stderr)
        return 2

    spec = json.loads(Path(args.cases).read_text())
    cases = spec["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]
    if args.kind:
        cases = [c for c in cases if c["kind"] in args.kind]
    # Paired assertions need their base, so pull those in even if filtered out.
    needed = {a["base"] for c in cases for a in c["assert"] if "base" in a}
    have = {c["id"] for c in cases}
    for c in spec["cases"]:
        if c["id"] in needed - have:
            cases.append(c)

    runs = len(cases) * args.repeat
    print(f"cases: {len(cases)}  repeat: {args.repeat}  runs: {runs}  model: {args.model}")
    print(f"estimated cost: ~${runs * 0.50:.2f} at ~$0.50/run\n")
    if args.dry_run:
        for c in cases:
            print(f"  [{c['kind']:<6}] {c['id']:<28} {c['task'][:64]}")
        return 0

    sandbox = Path(tempfile.mkdtemp(prefix="cortex-eval-"))
    results, cost = {}, 0.0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(run_case, c, args.model, sandbox, claude_bin): (c, i)
                       for c in cases for i in range(args.repeat)}
            for fut in concurrent.futures.as_completed(futures):
                case, _ = futures[fut]
                results.setdefault(case["id"], {"case": case, "runs": []})
                results[case["id"]]["runs"].append(fut.result())
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    # Collapse repeats: the modal route is the one asserted against; disagreement
    # across repeats is reported as instability rather than silently averaged away.
    for cid, r in results.items():
        routes = [x["route"] for x in r["runs"] if x.get("route")]
        cost += sum(x.get("cost_usd") or 0.0 for x in r["runs"])
        sigs = [f"{x['system']}>{x['pattern']}@{x['tier']}" for x in routes]
        top = max(set(sigs), key=sigs.count) if sigs else None
        r["modal"] = routes[sigs.index(top)] if routes else None
        r["stable"] = len(set(sigs)) <= 1
        # With no strict majority the "modal" route is an arbitrary pick among ties, so
        # asserting against it would report a pass or fail that another tie-break would
        # have reversed. Such cases are reported as indeterminate instead.
        r["indeterminate"] = bool(sigs) and len(sigs) > 1 and sigs.count(top) * 2 <= len(sigs)
        r["raw"] = next((x["raw"] for x in r["runs"] if x.get("raw")), "")

    rows = []
    tally = {"pass": 0, "fail": 0, "refused": 0, "unstable": 0}
    for cid, r in results.items():
        for a in r["case"]["assert"]:
            outcome, detail = check(a, cid, results)
            rows.append({"case": cid, "kind": r["case"]["kind"], "assert": a["type"],
                         "outcome": outcome, "detail": detail})
            tally[outcome] += 1

    order = {"fail": 0, "unstable": 1, "refused": 2, "pass": 3}
    print(f"{'CASE':<28} {'KIND':<7} {'RESULT':<8} DETAIL")
    print("-" * 92)
    for row in sorted(rows, key=lambda x: (order[x["outcome"]], x["case"])):
        print(f"{row['case']:<28} {row['kind']:<7} {row['outcome'].upper():<8} {row['detail']}")
    unstable = [c for c, r in results.items() if not r["stable"]]
    print("-" * 92)
    print(f"{tally['pass']} passed, {tally['fail']} failed, {tally['unstable']} unstable, "
          f"{tally['refused']} refused, {len(rows)} assertions   cost ${cost:.2f}")
    npass, nfail = tally["pass"], tally["fail"]
    if unstable:
        print(f"unstable across repeats (route varied): {', '.join(unstable)}")
    for cid, r in results.items():
        if not r["modal"]:
            print(f"  ! {cid}: no parseable route. raw={r['raw'][:90]!r}")

    out = Path(args.out) if args.out else CLAUDE_DIR / "eval" / \
        f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "repeat": args.repeat,
        # Pinning the inputs is what makes two runs comparable. A change in either
        # hash means a difference in results is explained, not a regression.
        "cortex_md_sha": sha(CLAUDE_DIR / "cortex.md"),
        "claude_md_sha": sha(CLAUDE_DIR / "CLAUDE.md"),
        "cases_sha": sha(args.cases),
        "cost_usd": round(cost, 4),
        "summary": {"passed": npass, "failed": nfail, "refused": tally["refused"],
                    "indeterminate": tally["unstable"], "varied_across_repeats": unstable},
        "assertions": rows,
        "results": {k: {"modal": v["modal"], "stable": v["stable"], "raw": v["raw"],
                        "runs": v["runs"]} for k, v in results.items()},
    }, indent=2))
    print(f"\nresults: {out}")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
