#!/usr/bin/env python3
"""replay_compare — re-route the frozen replay set and diff it against the last run.

WHAT THIS ANSWERS
    "Did editing cortex.md change how Cortex routes?" It needs no human labels, because
    the baseline is the previous run's own output rather than a judgement about what is
    correct. That makes it the half of the replay set that can run today.

WHAT IT CANNOT ANSWER
    Whether the new behaviour is *better*. Detecting change is not evaluating it. That
    needs ground truth from someone who is not the system under test, which is what the
    labelling sheet is for and why it is deliberately not filled in by a model.

THE NOISE PROBLEM, AND WHY THE AGGREGATE IS THE HEADLINE
    Routing is stochastic. Measured on this system: identical inputs minutes apart
    produced different routes on every case that was repeated. So a per-item difference
    between two single runs is not evidence of anything on its own — the same item flips
    without cortex.md moving at all.

    The aggregate tier distribution is far more stable than any individual item, so that
    is reported as the primary signal and per-item changes are labelled candidates rather
    than findings. Raising --repeat is what converts a candidate into a claim; at
    --repeat 1 this tool is a screen, not a verdict.

    Note that repeats reduce variance, they do not increase sample size. The statistical
    unit stays the item.

COMPARABILITY
    A run records the cortex.md hash and the model. Two runs whose hashes differ are
    answering different questions by construction, which is the point; two runs whose
    *models* differ are not comparable at all and the diff says so rather than pretending.
"""
import argparse
import concurrent.futures
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
RUNS_DIR = CLAUDE_DIR / "eval" / "replay-runs"

# Reuse the routing harness rather than growing a second one that can drift from it.
_re = SourceFileLoader("route_eval", str(HERE / "route_eval.py")).load_module()
TIERS = _re.TIERS


def load_set(path):
    d = json.loads(Path(path).read_text())
    return d, [{"id": i["id"], "task": i["task"], "class": i.get("class")} for i in d["items"]]


def run_once(items, model, jobs, batch_size):
    """Route every item. All items here are independent, so they batch freely — the
    isolation the paired cases need does not apply, and batching is ~5x cheaper."""
    sandbox = Path(tempfile.mkdtemp(prefix="replay-"))
    (sandbox / "minimal-settings.json").write_text("{}")
    out, cost = {}, 0.0
    try:
        chunks = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        claude = shutil.which("claude")
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            futs = [pool.submit(_re.run_batch, c, model, sandbox, claude) for c in chunks]
            for f in concurrent.futures.as_completed(futs):
                for cid, res in f.result().items():
                    out[cid] = res
                    cost += res.get("cost_usd") or 0.0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    return out, cost


def sig(route):
    return f"{route['system']} > {route['pattern']} @ {route['tier']}" if route else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default=str(CLAUDE_DIR / "eval" / "replay-set.json"))
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per item. Raises confidence in a per-item change; does NOT "
                         "increase sample size (default 1)")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--max-spend", type=float, default=5.0)
    ap.add_argument("--cost-per-session", type=float, default=0.53)
    ap.add_argument("--baseline", default=None, help="run file to diff against (default: latest)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    meta, items = load_set(args.set)
    sessions = -(-len(items) // args.batch_size) * args.repeat
    estimate = sessions * args.cost_per_session
    print(f"items: {len(items)}  repeat: {args.repeat}  sessions: {sessions}  model: {args.model}")
    print(f"estimated cost: ~${estimate:.2f} (ceiling ${args.max_spend:.2f})\n")
    if estimate > args.max_spend and not args.dry_run:
        print(f"refusing to start: estimate exceeds --max-spend.", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0

    per_item = {i["id"]: [] for i in items}
    total_cost = 0.0
    for r in range(args.repeat):
        res, cost = run_once(items, args.model, args.jobs, args.batch_size)
        total_cost += cost
        for cid, v in res.items():
            if v.get("route"):
                per_item[cid].append(v["route"])

    # Modal route per item, plus whether the item was stable across its own repeats.
    current = {}
    for cid, routes in per_item.items():
        sigs = [sig(x) for x in routes]
        current[cid] = {
            "route": max(set(sigs), key=sigs.count) if sigs else None,
            "stable": len(set(sigs)) <= 1,
            "observed": sigs,
        }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_path = RUNS_DIR / f"replay-{stamp}.json"
    run_path.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": args.model, "repeat": args.repeat,
        "cortex_md_sha": _re.sha(CLAUDE_DIR / "cortex.md"),
        "set_frozen_at": meta.get("frozen_at"),
        "cost_usd": round(total_cost, 4),
        "items": current,
    }, indent=2))

    tiers = Counter(v["route"].split("@ ")[-1].strip() for v in current.values() if v["route"])
    unstable = [c for c, v in current.items() if not v["stable"]]
    print(f"routed {sum(1 for v in current.values() if v['route'])}/{len(items)}  "
          f"cost ${total_cost:.2f}")
    print(f"tier mix: {dict(sorted(tiers.items()))}")
    if args.repeat > 1 and unstable:
        print(f"unstable across own repeats: {len(unstable)}/{len(items)}")

    # ---- diff against a prior run ------------------------------------------ #
    prior_files = sorted(p for p in RUNS_DIR.glob("replay-*.json") if p != run_path)
    baseline = Path(args.baseline) if args.baseline else (prior_files[-1] if prior_files else None)
    if not baseline:
        print(f"\nno prior run — this one is the baseline.\nsaved: {run_path}")
        return 0

    prev = json.loads(baseline.read_text())
    print(f"\ndiff vs {baseline.name}")
    if prev.get("model") != args.model:
        print(f"  !! model differs ({prev.get('model')} vs {args.model}) — NOT comparable. "
              f"Routing behaviour is a property of model and document together.")
        return 1
    same_doc = prev.get("cortex_md_sha") == _re.sha(CLAUDE_DIR / "cortex.md")
    print(f"  cortex.md: {'unchanged — any difference below is noise' if same_doc else 'CHANGED'}")

    changed = []
    for cid, v in current.items():
        before = (prev.get("items", {}).get(cid) or {}).get("route")
        if before and v["route"] and before != v["route"]:
            changed.append((cid, before, v["route"]))
    pt = Counter(x["route"].split("@ ")[-1].strip()
                 for x in prev.get("items", {}).values() if x.get("route"))
    print(f"  tier mix before: {dict(sorted(pt.items()))}")
    print(f"  tier mix after:  {dict(sorted(tiers.items()))}")
    print(f"  per-item changes: {len(changed)}/{len(items)}"
          f"{'  (candidates — single-run differences are within known noise)' if args.repeat == 1 else ''}")
    for cid, b, a in changed[:12]:
        print(f"    {cid}  {b}  ->  {a}")
    if len(changed) > 12:
        print(f"    … +{len(changed) - 12} more")
    print(f"\nsaved: {run_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
