#!/usr/bin/env python3
"""Retrieval-independent ceiling for `cortex hint`.

The baseline says hint is silent 88% of the time. The obvious inference is "retrieval is
too weak, make it semantic". This script tests that inference before anyone acts on it.

An ORACLE retriever is one that returns, from the prior pool, whichever entry is most
useful — i.e. it is allowed to cheat and look at the answer. No embedding model, no
reranker, no amount of MLX can beat it. If the oracle is also bad, the bottleneck is the
data, not the retrieval, and a better retriever cannot fix it.

Also reports the trivial no-retrieval baselines, because a proposal has to beat those to
be worth any code at all.
"""
import json
from collections import Counter

LOG = "/Users/amit/.claude/cortex-log.jsonl"


def main():
    rows = [json.loads(l) for l in open(LOG) if l.strip()]
    entries = [r for r in rows if r.get("task")]
    entries.sort(key=lambda r: r.get("ts", ""))

    full = lambda e: (e.get("system"), e.get("pattern"), e.get("tier"))
    syspat = lambda e: (e.get("system"), e.get("pattern"))
    tier = lambda e: e.get("tier")

    print("=" * 74)
    print("LABEL SPACE — how fragmented is the thing we are trying to predict?")
    print("=" * 74)
    for name, key in (("system+pattern+tier", full), ("system+pattern", syspat), ("tier", tier)):
        c = Counter(key(e) for e in entries)
        singles = sum(1 for v in c.values() if v == 1)
        print(f"  {name:<22} {len(c):3d} distinct over {len(entries)} entries"
              f"   ({len(entries)/len(c):.1f} examples each)"
              f"   {singles} seen exactly once ({100*singles/len(c):.0f}%)")

    print()
    print("=" * 74)
    print("ORACLE CEILING — can the right answer even be found in prior routes?")
    print("  'available' = at least one earlier entry carries the same label.")
    print("  This is the hard ceiling on top-1 accuracy for ANY retriever.")
    print("=" * 74)

    for name, key in (("system+pattern+tier", full), ("system+pattern", syspat), ("tier", tier)):
        avail = avail_cls = n = 0
        for i, e in enumerate(entries):
            pool = entries[:i]
            if len(pool) < 3:
                continue
            n += 1
            if any(key(p) == key(e) for p in pool):
                avail += 1
            same_cls = [p for p in pool if p.get("class") == e.get("class")]
            if any(key(p) == key(e) for p in same_cls):
                avail_cls += 1
        print(f"  {name:<22} any prior match {avail:3d}/{n} = {100*avail/n:5.1f}%"
              f"    within same class {avail_cls:3d}/{n} = {100*avail_cls/n:5.1f}%")

    print()
    print("=" * 74)
    print("NO-RETRIEVAL BASELINES — what you get for free, with zero code")
    print("=" * 74)
    for name, key in (("system+pattern+tier", full), ("system+pattern", syspat), ("tier", tier)):
        # prequential: always predict the most common label seen so far
        hits = n = 0
        seen = Counter()
        for i, e in enumerate(entries):
            if i >= 3:
                n += 1
                if seen and seen.most_common(1)[0][0] == key(e):
                    hits += 1
            seen[key(e)] += 1
        print(f"  {name:<22} always-most-common-so-far  {hits:3d}/{n} = {100*hits/n:5.1f}%")

    print()
    print("=" * 74)
    print("HEADROOM SUMMARY")
    print("=" * 74)
    # oracle for full route within class, vs current jaccard top-1 (from baseline: ~12.5%)
    print("  Current Jaccard top-1 full-route agreement (class-filtered, 0.15): 12.5% of the")
    print("  12.3% of queries where it fires => 1.5% of all routing decisions get a correct")
    print("  top-1 suggestion. Compare that against the oracle ceiling above.")


if __name__ == "__main__":
    main()
