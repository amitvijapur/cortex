#!/usr/bin/env python3
"""Two controls that decide whether a semantic retriever is worth building.

CONTROL 1 — matched-subset tier check.
  Jaccard looks strong on tier (81% when it fires). But it only fires on queries that
  have a lexical near-duplicate in the log, and repeat work tends to reuse its tier. So
  the comparison must be against the majority-tier baseline ON THE SAME SUBSET, not
  against the baseline over all queries. This is the exact trap that flattered the BM25F
  ranker.

CONTROL 2 — recall of the findable.
  Silence is only a defect when there was something to find. Split queries into those
  where a same-route prior entry EXISTS (findable) and those where it does not. On the
  findable half, how often does Jaccard surface it in the top 5? That gap is the entire
  headroom a semantic embedding model could ever recover.
"""
import json
import re
from collections import Counter, defaultdict

LOG = "/Users/amit/.claude/cortex-log.jsonl"
STOP = {"the", "and", "for", "with", "this", "that", "from", "into", "onto",
        "a", "an", "of", "in", "on", "at", "to", "is", "be", "as", "by",
        "or", "if", "it", "but", "not", "so", "do", "we", "i", "my", "me"}


def tokens(s):
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) >= 3 and t not in STOP}


def jaccard_rank(query, pool, min_sim):
    tq = tokens(query)
    if not tq:
        return []
    scored = []
    for e in pool:
        te = tokens(e.get("task", ""))
        if not te:
            continue
        j = len(tq & te) / len(tq | te)
        if j >= min_sim:
            scored.append((j, e))
    scored.sort(key=lambda x: -x[0])
    return scored


def main():
    rows = [json.loads(l) for l in open(LOG) if l.strip()]
    entries = [r for r in rows if r.get("task")]
    entries.sort(key=lambda r: r.get("ts", ""))
    full = lambda e: (e.get("system"), e.get("pattern"), e.get("tier"))

    MIN_SIM, TOP_N = 0.15, 5

    print("=" * 78)
    print("CONTROL 1 — tier accuracy on the MATCHED subset where Jaccard fires")
    print("=" * 78)
    fired_idx = []
    for i, e in enumerate(entries):
        pool = [p for p in entries[:i] if p.get("class") == e.get("class")]
        if len(pool) < 3:
            continue
        r = jaccard_rank(e.get("task", ""), pool, MIN_SIM)
        if r:
            fired_idx.append((i, e, pool, r))

    jac_hits = maj_hits = 0
    for i, e, pool, r in fired_idx:
        # Jaccard's tier suggestion = weighted top-1 tier among top-N matches
        tally = defaultdict(float)
        for sim, m in r[:TOP_N]:
            tally[m.get("tier")] += sim
        if max(tally.items(), key=lambda x: x[1])[0] == e.get("tier"):
            jac_hits += 1
        # Majority baseline computed on the SAME pool available at that moment
        pool_maj = Counter(p.get("tier") for p in pool).most_common(1)[0][0]
        if pool_maj == e.get("tier"):
            maj_hits += 1

    n = len(fired_idx)
    print(f"  subset size (queries where Jaccard fires)   {n}")
    print(f"  Jaccard top-1 tier correct                  {jac_hits}/{n} = {100*jac_hits/n:5.1f}%")
    print(f"  majority-tier-so-far on same subset         {maj_hits}/{n} = {100*maj_hits/n:5.1f}%")
    delta = 100 * (jac_hits - maj_hits) / n
    print(f"  --> retrieval contributes                   {delta:+.1f} points")
    if abs(jac_hits - maj_hits) <= 2:
        print("      (within noise at this sample size — treat as no effect)")

    print()
    print("=" * 78)
    print("CONTROL 2 — recall of the findable (the only headroom that exists)")
    print("=" * 78)
    findable = notfindable = 0
    found_in_topn = 0
    fired_but_unfindable = 0
    for i, e in enumerate(entries):
        pool = [p for p in entries[:i] if p.get("class") == e.get("class")]
        if len(pool) < 3:
            continue
        has_match = any(full(p) == full(e) for p in pool)
        r = jaccard_rank(e.get("task", ""), pool, MIN_SIM)
        if has_match:
            findable += 1
            if any(full(m) == full(e) for _, m in r[:TOP_N]):
                found_in_topn += 1
        else:
            notfindable += 1
            if r:
                fired_but_unfindable += 1

    tot = findable + notfindable
    print(f"  queries where a same-route prior EXISTS     {findable}/{tot} = {100*findable/tot:5.1f}%")
    print(f"    ...and Jaccard surfaced it in top-{TOP_N}       {found_in_topn}/{findable} = "
          f"{100*found_in_topn/findable:5.1f}%   <-- RECALL")
    print(f"    ...missed by Jaccard (semantic headroom)  {findable-found_in_topn}/{findable} = "
          f"{100*(findable-found_in_topn)/findable:5.1f}%")
    print()
    print(f"  queries where NO same-route prior exists    {notfindable}/{tot} = {100*notfindable/tot:5.1f}%")
    print(f"    ...Jaccard fired anyway (noise/misleads)  {fired_but_unfindable}/{notfindable} = "
          f"{100*fired_but_unfindable/notfindable:5.1f}%")
    print()
    print("  MAXIMUM ABSOLUTE GAIN from perfect semantic retrieval:")
    print(f"    {findable-found_in_topn} of {tot} routing decisions = "
          f"{100*(findable-found_in_topn)/tot:.1f}% of all decisions could newly see a correct")
    print("    prior route in their top-5. Whether seeing it changes the route is a")
    print("    separate question this measurement does NOT answer.")


if __name__ == "__main__":
    main()
