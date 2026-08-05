#!/usr/bin/env python3
"""build_replay_set — freeze a stratified task set for paired routing comparison.

WHAT THIS IS FOR
    Regression on routing quality cannot be done by comparing rates across time windows,
    because the task mix changes and the sample is far too small. Detecting a 5-point
    quality drop that way needs roughly 821 routes per arm, about 19 months at current
    volume. Comparing the SAME frozen items before and after a change is about an order
    of magnitude cheaper, which is what turns this from impossible into a 30-50 item
    exercise.

    So this set is not a benchmark of Cortex in general. It is a fixed probe, re-run
    whenever cortex.md changes, where the only thing that varies is the document.

WHY THE LABELLING IS BLIND
    The worksheet deliberately does NOT show what was actually routed at the time.
    Anchoring is the obvious failure here: shown a previous answer, a labeller mostly
    ratifies it, and the set then measures agreement with history rather than judgement.
    The original route is kept in the JSON for later comparison and withheld from the
    human until after labelling.

WHAT A LABEL MEANS
    Not "what did Cortex do" and not "what is defensible", but "what should this have
    been routed to". Where more than one route is genuinely reasonable, say so: an item
    with a real tie is evidence about the protocol, and scoring it as a miss would
    manufacture a failure that is not there.
"""
import argparse
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
LOG_PATH = CLAUDE_DIR / "cortex-log.jsonl"
DEFAULT_OUT = CLAUDE_DIR / "eval" / "replay-set.json"
DEFAULT_SHEET = (Path.home() / "Desktop/Personal/Obsidian Folders/2nd Brain"
                 / "Claude Code/Cortex/Replay Set.md")


def sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=40, help="target item count (default 40)")
    ap.add_argument("--seed", type=int, default=20260805,
                    help="fixed so the set is reproducible; changing it changes the set")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--sheet", default=str(DEFAULT_SHEET))
    args = ap.parse_args()

    rows = [json.loads(l) for l in LOG_PATH.read_text().splitlines() if l.strip()]
    routes = [r for r in rows if not r.get("event") or r.get("event") == "route"]
    # One entry per distinct task. Duplicates would weight an item twice in the paired
    # comparison without adding information.
    seen, pool = set(), []
    for r in routes:
        key = (r.get("task") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        pool.append(r)

    by_class = defaultdict(list)
    for r in pool:
        by_class[r.get("class") or "unknown"].append(r)

    # Stratify proportionally, but floor every class at 2 so the rare ones (debug, design)
    # are represented at all. A set that omits a class cannot detect a regression in it.
    rng = random.Random(args.seed)
    picked, total = [], len(pool)
    for cls, items in sorted(by_class.items()):
        share = max(2, round(args.size * len(items) / total))
        rng.shuffle(items)
        picked.extend(items[:min(share, len(items))])
    rng.shuffle(picked)

    items = []
    for i, r in enumerate(picked):
        items.append({
            "id": f"rp{i:03d}",
            "task": r.get("task"),
            "task_hash": r.get("task_hash"),
            "class": r.get("class"),
            # Withheld from the worksheet. Present here for post-labelling comparison.
            "historical_route": {"system": r.get("system"), "pattern": r.get("pattern"),
                                 "agent": r.get("agent"), "tier": r.get("tier")},
            "label": None,        # what it SHOULD route to, in Amit's judgement
            "label_tie": None,    # set true when more than one route is genuinely right
            "label_note": None,
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "_status": "UNLABELLED — blind. Do not reveal historical_route before labelling.",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        # The set is frozen against a document version. If this hash moves, results before
        # and after are answering different questions and must not be pooled.
        "cortex_md_sha": sha(CLAUDE_DIR / "cortex.md"),
        "seed": args.seed,
        "pool_size": total,
        "items": items,
    }, indent=2))

    sheet = ["---", "tags: [cortex, worksheet]", "status: unlabelled", "---", "",
             "# Replay Set", "",
             f"{len(items)} frozen tasks sampled from the routing log. Labelling these once "
             "gives paired before/after comparison on any cortex.md change, which is the "
             "only affordable way to detect a routing regression at this volume.", "",
             "## How to label", "",
             "For each task write the route you think it **should** get:", "",
             "```", "System > Pattern [> Agent] @ L<n>", "```", "",
             "- If two routes are genuinely both right, write both and mark `TIE`. "
             "A real tie is information about the protocol; scoring it as a miss would "
             "invent a failure that isn't there.",
             "- If you can't decide, leave it blank. Blanks are fine, guesses are not.", "",
             "> **You are labelling blind on purpose.** What was actually routed at the "
             "time is stored but deliberately not shown. If you saw it you would mostly "
             "ratify it, and the set would end up measuring agreement with history "
             "instead of your judgement.", ""]
    for cls in sorted({i["class"] for i in items}):
        sheet += ["---", "", f"## {cls}", ""]
        for it in [x for x in items if x["class"] == cls]:
            sheet += [f"**{it['id']}** — {it['task']}", "- **route →** ", ""]
    Path(args.sheet).parent.mkdir(parents=True, exist_ok=True)
    Path(args.sheet).write_text("\n".join(sheet))

    print(f"pool: {total} distinct tasks -> froze {len(items)}")
    print(f"by class: {dict(Counter(i['class'] for i in items))}")
    print(f"set:   {out}")
    print(f"sheet: {args.sheet}")


if __name__ == "__main__":
    main()
