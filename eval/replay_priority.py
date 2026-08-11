#!/usr/bin/env python3
"""replay_priority — pick the items in the frozen replay set that are worth labelling first.

WHY A SUBSET
    42 items is roughly two hours of judgement, and most of that time buys little. On a
    task whose routing is obvious, a label just confirms what everyone already agreed;
    the discriminating power sits in the items where routing is genuinely contested.
    Labelling 12-15 of those recovers most of the signal for a fraction of the sitting.

    The frozen set is NOT modified. It stays 42 items so the label-free regression
    comparison keeps its full sample; this only chooses a labelling order.

HOW "CONTESTED" IS ESTIMATED WITHOUT LABELS
    Four proxies, each with a reason:

      tier L3/L4          the anti-inflation rule is the largest rule in cortex.md, and
                          it is a rule about *not* reaching for a high tier. Errors there
                          are the ones the protocol most wants caught.
      minority route      the (class, system > pattern) combination is rare in the log.
                          A route the system has taken once is a route it was less sure
                          about than one it has taken seventeen times.
      fan-out             the historical route declared parallel agents. The Domain-breadth
                          heuristic is where routing decisions are hardest and where the
                          log shows the most invention.
      task breadth        longer, multi-clause tasks. Short imperative tasks are usually
                          unambiguous and cheap to route.

    These are heuristics for *ordering*, not claims about correctness. The honest test of
    whether an item is contested is whether repeated runs disagree on it, and that costs
    money to measure; if a repeat run ever shows instability, prefer that evidence to this.
"""
import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
DEFAULT_SHEET = (Path.home() / "Desktop/Personal/Obsidian Folders/2nd Brain"
                 / "Claude Code/Cortex/Replay Set (short).md")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default=str(CLAUDE_DIR / "eval" / "replay-set.json"))
    ap.add_argument("--log", default=str(CLAUDE_DIR / "cortex-log.jsonl"))
    ap.add_argument("--top", type=int, default=14)
    ap.add_argument("--sheet", default=str(DEFAULT_SHEET))
    args = ap.parse_args()

    items = json.loads(Path(args.set).read_text())["items"]
    rows = [json.loads(l) for l in Path(args.log).read_text().splitlines() if l.strip()]
    combo = Counter((r.get("class"), f"{r.get('system')} > {r.get('pattern')}")
                    for r in rows if not r.get("event") or r.get("event") == "route")

    scored = []
    for it in items:
        h = it.get("historical_route") or {}
        words = len(re.findall(r"\w+", it["task"] or ""))
        s = 0
        if h.get("tier") in ("L3", "L4"):
            s += 2
        if combo.get((it.get("class"), f"{h.get('system')} > {h.get('pattern')}"), 0) <= 2:
            s += 2
        if "∥" in (h.get("agent") or ""):
            s += 1
        if words >= 14:
            s += 1
        if words <= 6:
            s -= 2
        scored.append((s, it))

    scored.sort(key=lambda x: -x[0])
    picked, seen_class = [], set()
    for s, it in scored:                      # take the best, then backfill class coverage
        if len(picked) < args.top:
            picked.append(it); seen_class.add(it.get("class"))
    for s, it in scored:
        if it.get("class") not in seen_class:
            picked.append(it); seen_class.add(it.get("class"))

    sheet = ["---", "tags: [cortex, worksheet]", "status: unlabelled", "---", "",
             "# Replay Set — short list", "",
             f"The {len(picked)} items from the frozen 42 where routing is most likely to be "
             "contested, so a shorter sitting still buys most of the discriminating power. "
             "The full set stays frozen at 42 for the label-free regression comparison; this "
             "only chooses what to label first.", "",
             "## How to label", "",
             "Write the route you think each task **should** get:", "",
             "```", "System > Pattern [> Agent] @ L<n>", "```", "",
             "- Two routes genuinely both right? Write both, mark `TIE`. A real tie is "
             "information about the protocol, not a miss.",
             "- Can't decide? Leave it blank. Blanks are fine, guesses corrupt everything "
             "built on them.", "",
             "> Still blind on purpose: what was actually routed at the time is stored and "
             "deliberately not shown, so this measures your judgement rather than your "
             "agreement with history.", ""]
    for cls in sorted({i.get("class") for i in picked}):
        sheet += [f"## {cls}", ""]
        for it in [x for x in picked if x.get("class") == cls]:
            sheet += [f"**{it['id']}** — {it['task']}", "- **route →** ", ""]

    Path(args.sheet).parent.mkdir(parents=True, exist_ok=True)
    Path(args.sheet).write_text("\n".join(sheet))
    print(f"picked {len(picked)} of {len(items)}   classes: {dict(Counter(i.get('class') for i in picked))}")
    print(f"sheet: {args.sheet}")


if __name__ == "__main__":
    main()
