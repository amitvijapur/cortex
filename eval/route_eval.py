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
import re
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
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

BATCH_PROMPT = """Route each task below independently under the Cortex protocol. Do not
perform any of them. Do not use tools, do not run commands, do not log anything.

Treat every task on its own merits. Do not let your answer to one task influence another.

Output exactly one line per task, numbered to match the input, in the form
'N. System > Pattern [> Agent] @ L<n>' with optional [tags]. No explanation, no preamble.

{tasks}"""


def sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def atomic_write(path, data):
    """Publish a complete report (or evidence copy), never a truncated snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".report-",
                                         delete=False) as f:
            temp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def write_report(path, report):
    atomic_write(path, json.dumps(report, indent=2).encode("utf-8"))


def run_inputs(args, cases, batched):
    """Fingerprint the inputs and execution shape, not just the routing document."""
    return {
        "model": args.model,
        "cortex_md_sha": sha(CLAUDE_DIR / "cortex.md"),
        "claude_md_sha": sha(CLAUDE_DIR / "CLAUDE.md"),
        "cases_sha": sha(args.cases),
        "harness_sha": sha(__file__),
        "cli_sha": sha(CORTEX_BIN),
        "cases": cases,
        "repeat": args.repeat,
        "minimal_env": args.minimal_env,
        "no_batch": args.no_batch,
        "batched_cases": [c["id"] for c in batched],
    }


def successful_results(results, cases, repeat):
    """Require every requested execution and assertion to succeed before reuse."""
    if not cases or repeat < 1 or set(results) != {c["id"] for c in cases}:
        return False
    for c in cases:
        r = results[c["id"]]
        runs = r.get("runs", [])
        if (len(runs) != repeat or not r.get("modal") or r.get("stable") is not True
                or r.get("indeterminate")
                or any(x.get("error") or not x.get("route") for x in runs)):
            return False
        if any(x["route"] != r["modal"] for x in runs):
            return False
        if is_refusal(r["modal"]):
            return False
        if any(check(a, c["id"], results)[0] != "pass" for a in c["assert"]):
            return False
    return True


def reusable_run(last, inputs):
    """Legacy, malformed, failed and incomplete reports are cache misses."""
    try:
        return (last.get("successful") is True
                and last.get("inputs") == inputs
                and all(inputs[k] for k in
                        ("cortex_md_sha", "claude_md_sha", "cases_sha", "harness_sha", "cli_sha"))
                and successful_results(last["results"], inputs["cases"], inputs["repeat"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


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


def run_case(case, model, sandbox, claude_bin, minimal_env=False):
    env = dict(os.environ, CORTEX_HOME=str(sandbox))
    cmd = [claude_bin, "-p", PROMPT.format(task=case["task"]),
           "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--model", model]
    if minimal_env:
        # Intended to cut the per-run cost by not booting the whole framework for one
        # short line. Measured 2026-08-05: it does not. --settings only replaces the
        # settings file; agents, skills and CLAUDE.md still load from the config dir,
        # and MCP was already ruled out (cache_read identical with and without it).
        # The untested lever is the config directory itself. Kept for the isolation it
        # does provide (no hooks, no MCP), not for cost.
        cmd += ["--settings", str(sandbox / "minimal-settings.json"), "--strict-mcp-config"]
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        payload = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "cost_usd": 0.0}
    except (json.JSONDecodeError, ValueError):
        return {"error": f"unparseable CLI output: {proc.stdout[:200]}", "cost_usd": 0.0}

    if not isinstance(payload, dict) or proc.returncode or payload.get("is_error"):
        return {"error": f"CLI failed (exit {proc.returncode})", "cost_usd":
                (payload.get("total_cost_usd") or 0.0) if isinstance(payload, dict) else 0.0}
    parsed, raw = extract_route(payload.get("result", ""))
    return {
        "raw": raw,
        "route": parsed,
        "cost_usd": payload.get("total_cost_usd") or 0.0,
        "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "error": None if parsed else "no parseable routing line",
    }


def run_batch(cases, model, sandbox, claude_bin):
    """Route several independent cases in one session.

    Isolation is only load-bearing for the paired comparisons, where an anchored answer
    would corrupt the very delta being measured. For independent cases the saving is
    large (one session instead of N) and the residual anchoring risk is accepted and
    recorded, not pretended away.
    """
    env = dict(os.environ, CORTEX_HOME=str(sandbox))
    listing = "\n".join(f"{i+1}. {c['task']}" for i, c in enumerate(cases))
    cmd = [claude_bin, "-p", BATCH_PROMPT.format(tasks=listing),
           "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--model", model]
    out = {c["id"]: {"error": "missing from batch response", "cost_usd": 0.0} for c in cases}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
        payload = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        for v in out.values():
            v["error"] = f"batch failed: {type(exc).__name__}"
        return out

    if not isinstance(payload, dict) or proc.returncode or payload.get("is_error"):
        for v in out.values():
            v["error"] = f"batch CLI failed (exit {proc.returncode})"
        if cases and isinstance(payload, dict):
            out[cases[0]["id"]]["cost_usd"] = payload.get("total_cost_usd") or 0.0
        return out
    cost = payload.get("total_cost_usd") or 0.0
    body = payload.get("result") or ""
    for c in cases:  # keep the raw response so a dropped case is diagnosable offline
        out[c["id"]]["batch_raw"] = body[:2000]
    for line in body.splitlines():
        line = line.strip().strip("`").strip()
        m = re.match(r"^(\d+)[.)]\s*(.+)$", line)
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if not 0 <= idx < len(cases):
            continue
        try:
            parsed = parse_route(m.group(2).strip())
        except ValueError:
            continue
        # Cost is attributed to the first case only so the run total stays truthful;
        # dividing it across cases would invent per-case figures that do not exist.
        out[cases[idx]["id"]] = {"raw": m.group(2).strip(), "route": parsed, "error": None,
                                 "batched": True, "duration_s": None,
                                 "cost_usd": cost if idx == 0 else 0.0}

    # The model does not reliably return one line per task. Cases it dropped are re-run
    # individually: scoring them as "no route produced" would report protocol failures
    # that never happened, which is the exact false-signal this suite exists to avoid.
    missing = [c for c in cases if out[c["id"]].get("route") is None]
    for c in missing:
        retry = run_case(c, model, sandbox, claude_bin)
        retry["batch_retry"] = True
        retry["batch_raw"] = body[:2000]
        out[c["id"]] = retry
    return out


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
    ap.add_argument("--minimal-env", action="store_true",
                    help="MEASURED INEFFECTIVE: swaps the settings file and drops MCP, but "
                         "agents/skills/CLAUDE.md still load from the config dir, so cost is "
                         "unchanged ($0.58/run vs $0.53 baseline, 2026-08-05)")
    ap.add_argument("--max-spend", type=float, default=5.0,
                    help="refuse to start a run whose estimate exceeds this (default: $5)")
    ap.add_argument("--cost-per-run", type=float, default=0.53,
                    help="observed per-run cost used for the estimate (default: 0.53)")
    ap.add_argument("--no-batch", action="store_true",
                    help="isolate every case. By default independent cases share one "
                         "session (much cheaper) and any the model drops are re-run "
                         "individually. Paired cases are never batched")
    ap.add_argument("--if-changed", action="store_true",
                    help="skip only after a successful run with matching inputs and coverage")
    args = ap.parse_args()
    if args.repeat < 1 or args.jobs < 1:
        ap.error("--repeat and --jobs must be positive")

    claude_bin = shutil.which("claude")
    if not claude_bin and not args.dry_run:
        print("error: `claude` not found on PATH", file=sys.stderr)
        return 2

    spec = json.loads(Path(args.cases).read_text())
    ids = [c["id"] for c in spec["cases"]]
    if len(ids) != len(set(ids)):
        ap.error("case ids must be unique")
    if args.only and set(args.only) - set(ids):
        ap.error("--only contains unknown case ids")
    cases = spec["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]
    if args.kind:
        cases = [c for c in cases if c["kind"] in args.kind]
    # Paired assertions need their base, so pull those in even if filtered out.
    while True:
        needed = {a["base"] for c in cases for a in c["assert"] if "base" in a}
        if needed - set(ids):
            ap.error("paired assertion references an unknown base case")
        have = {c["id"] for c in cases}
        if not needed - have:
            break
        cases.extend(c for c in spec["cases"] if c["id"] in needed - have)
    if not cases:
        ap.error("no cases selected")

    # Paired cases and anything they reference must stay isolated: a shared session
    # would let the base answer anchor the transformed one, which is exactly the delta
    # under measurement.
    pinned = set(needed) | {c["id"] for c in cases
                            if c["kind"] == "paired" or any("base" in a for a in c["assert"])}
    if args.no_batch:
        isolated, batched = list(cases), []
    else:
        isolated = [c for c in cases if c["id"] in pinned]
        batched = [c for c in cases if c["id"] not in pinned]

    runs = len(cases) * args.repeat
    sessions = (len(isolated) + (1 if batched else 0)) * args.repeat
    estimate = sessions * args.cost_per_run
    print(f"cases: {len(cases)}  repeat: {args.repeat}  runs: {runs}  model: {args.model}"
          f"{'  [minimal-env]' if args.minimal_env else ''}")
    print(f"sessions: {sessions} ({len(isolated)} isolated"
          f"{f' + 1 batch of {len(batched)}' if batched else ''}) x{args.repeat}")
    print(f"estimated cost: ~${estimate:.2f} at ~${args.cost_per_run:.2f}/session "
          f"(ceiling ${args.max_spend:.2f})\n")

    inputs = run_inputs(args, cases, batched)
    if args.if_changed and not args.dry_run:
        prior = ([Path(args.out)] if args.out else
                 sorted((CLAUDE_DIR / "eval").glob("run-*.json"),
                        # Order old second-precision and new microsecond names together.
                        key=lambda p: p.stem.replace("Z", "")))
        if prior:
            try:
                last = json.loads(prior[-1].read_text())
            except (OSError, ValueError):
                last = None
            if reusable_run(last, inputs):
                print(f"successful run {prior[-1].name} matches all inputs and coverage; skipping")
                return 0

    if estimate > args.max_spend and not args.dry_run:
        print(f"refusing to start: estimate ${estimate:.2f} exceeds --max-spend "
              f"${args.max_spend:.2f}. Narrow with --only/--kind, lower --repeat, "
              f"add --minimal-env, or raise the ceiling deliberately.", file=sys.stderr)
        return 2

    if args.dry_run:
        for c in cases:
            print(f"  [{c['kind']:<6}] {c['id']:<28} {c['task'][:64]}")
        return 0

    started = datetime.now(timezone.utc)
    attempt_id = uuid.uuid4().hex
    out = Path(args.out) if args.out else CLAUDE_DIR / "eval" / \
        f"run-{started.strftime('%Y%m%dT%H%M%S.%fZ')}-{attempt_id}.json"
    if out.exists():
        # Explicit --out reuses a name. Preserve the exact previous evidence before
        # replacing it, including failed or malformed reports, outside cache lookup.
        archive = out.parent / f".{out.name}.history" / f"{attempt_id}.json"
        atomic_write(archive, out.read_bytes())
    attempt = {"ts": started.isoformat(), "attempt_id": attempt_id,
               "attempt_status": "incomplete", "successful": False,
               "inputs": inputs, "results": {}}
    # Persist before launching anything: exceptions, interrupts and process death
    # must leave a cache miss, rather than resurrecting an older successful run.
    write_report(out, attempt)

    sandbox = Path(tempfile.mkdtemp(prefix="cortex-eval-"))
    (sandbox / "minimal-settings.json").write_text("{}")
    results, cost = {}, 0.0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(run_case, c, args.model, sandbox, claude_bin,
                                   args.minimal_env): c
                       for c in isolated for _ in range(args.repeat)}
            batch_futs = [pool.submit(run_batch, batched, args.model, sandbox, claude_bin)
                          for _ in range(args.repeat)] if batched else []
            for fut in concurrent.futures.as_completed(list(futures) + batch_futs):
                if fut in futures:
                    case = futures[fut]
                    results.setdefault(case["id"], {"case": case, "runs": []})
                    results[case["id"]]["runs"].append(fut.result())
                else:
                    for cid, res in fut.result().items():
                        case = next(c for c in batched if c["id"] == cid)
                        results.setdefault(cid, {"case": case, "runs": []})
                        results[cid]["runs"].append(res)
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

    successful = (successful_results(results, cases, args.repeat)
                  and inputs == run_inputs(args, cases, batched))
    write_report(out, {
        **attempt,
        "attempt_status": "complete",
        "completed_ts": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "minimal_env": args.minimal_env,
        "sessions": sessions,
        "batched_cases": [c["id"] for c in batched],
        "repeat": args.repeat,
        "inputs": inputs,
        "successful": successful,
        # Pinning the inputs is what makes two runs comparable. A change in either
        # hash means a difference in results is explained, not a regression.
        "cortex_md_sha": inputs["cortex_md_sha"],
        "claude_md_sha": inputs["claude_md_sha"],
        "cases_sha": inputs["cases_sha"],
        "cost_usd": round(cost, 4),
        "summary": {"passed": npass, "failed": nfail, "refused": tally["refused"],
                    "indeterminate": tally["unstable"], "varied_across_repeats": unstable},
        "assertions": rows,
        "results": {k: {"modal": v["modal"], "stable": v["stable"], "raw": v["raw"],
                        "runs": v["runs"]} for k, v in results.items()},
    })
    print(f"\nresults: {out}")
    return 0 if successful else 1


if __name__ == "__main__":
    sys.exit(main())
