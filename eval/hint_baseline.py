#!/usr/bin/env python3
"""Baseline measurement for `cortex hint` retrieval.

Replays the log in chronological order. For each entry i, the query is entry i's task
and the pool is entries 0..i-1 — which is exactly what hint could have seen at the
moment that route was decided. Anything else (full leave-one-out over the whole log)
leaks the future and inflates coverage.

Reports:
  A. Fire rate    — how often hint returns anything at all
  B. Agreement    — when it fires, does its top suggestion match the route actually taken
  C. Similarity   — distribution of the best match score
"""
import json
import re
import sys
from collections import Counter, defaultdict

LOG = "/Users/amit/.claude/cortex-log.jsonl"

STOP = {"the", "and", "for", "with", "this", "that", "from", "into", "onto",
        "a", "an", "of", "in", "on", "at", "to", "is", "be", "as", "by",
        "or", "if", "it", "but", "not", "so", "do", "we", "i", "my", "me"}

OUTCOME_WEIGHTS = {"shipped": 1.0, "partial": 0.5, "corrected": -1.0, "abandoned": -0.5}
UNSCORED_WEIGHT = 0.3


def tokens(s):
    out = set()
    for tok in re.split(r"[^a-z0-9]+", s.lower()):
        if len(tok) >= 3 and tok not in STOP:
            out.add(tok)
    return out


def hint(query, pool, min_sim, top_n=5):
    """Mirror of cmd_hint's scoring. Returns (matches, ranked_routes)."""
    target = tokens(query)
    if not target:
        return [], []
    scored = []
    for e in pool:
        toks = tokens(e.get("task", ""))
        if not toks:
            continue
        j = len(target & toks) / len(target | toks)
        if j >= min_sim:
            scored.append((j, e))
    if not scored:
        return [], []
    scored.sort(key=lambda x: -x[0])
    top = scored[:top_n]
    tally = defaultdict(float)
    for sim, e in top:
        route = (e.get("system"), e.get("pattern"), e.get("tier"))
        tally[route] += sim * OUTCOME_WEIGHTS.get(e.get("outcome"), UNSCORED_WEIGHT)
    ranked = sorted(tally.items(), key=lambda x: -x[1])
    return top, ranked


def run(entries, min_sim, class_filter, label):
    fired = 0
    total = 0
    agree_route = 0        # system+pattern+tier all match actual
    agree_sys_pat = 0      # system+pattern match
    agree_tier = 0
    best_sims = []
    neg_top = 0            # top suggestion had a negative (anti-signal) score

    for i, e in enumerate(entries):
        pool = entries[:i]
        if class_filter:
            pool = [p for p in pool if p.get("class") == e.get("class")]
        if len(pool) < 3:
            continue        # too early in the log to be a fair test
        total += 1
        matches, ranked = hint(e.get("task", ""), pool, min_sim)
        if not matches:
            continue
        fired += 1
        best_sims.append(matches[0][0])
        (sys_, pat, tier), score = ranked[0]
        if score < 0:
            neg_top += 1
        if sys_ == e.get("system") and pat == e.get("pattern") and tier == e.get("tier"):
            agree_route += 1
        if sys_ == e.get("system") and pat == e.get("pattern"):
            agree_sys_pat += 1
        if tier == e.get("tier"):
            agree_tier += 1

    pct = lambda n, d: f"{100*n/d:5.1f}%" if d else "  n/a"
    print(f"\n=== {label} (min_similarity={min_sim}, class_filter={class_filter}) ===")
    print(f"  queries evaluated          {total}")
    print(f"  A. fire rate               {fired}/{total}  {pct(fired,total)}   "
          f"(silent {pct(total-fired,total)})")
    if fired:
        print(f"  B. top-1 == actual route   {agree_route}/{fired}  {pct(agree_route,fired)}"
              "   [system+pattern+tier]")
        print(f"     top-1 system+pattern    {agree_sys_pat}/{fired}  {pct(agree_sys_pat,fired)}")
        print(f"     top-1 tier              {agree_tier}/{fired}  {pct(agree_tier,fired)}")
        print(f"     top-1 score negative    {neg_top}/{fired}  {pct(neg_top,fired)}")
        best_sims.sort()
        n = len(best_sims)
        print(f"  C. best-match similarity   min {best_sims[0]:.3f}  "
              f"p50 {best_sims[n//2]:.3f}  p90 {best_sims[int(n*0.9)]:.3f}  "
              f"max {best_sims[-1]:.3f}")
    return {"total": total, "fired": fired, "agree_route": agree_route}


def main():
    rows = [json.loads(l) for l in open(LOG) if l.strip()]
    entries = [r for r in rows if r.get("task")]
    entries.sort(key=lambda r: r.get("ts", ""))
    print(f"log: {len(rows)} rows, {len(entries)} routed entries")
    print(f"date range: {entries[0]['ts']} .. {entries[-1]['ts']}")
    print("\nclass distribution:", dict(Counter(e.get("class") for e in entries).most_common()))
    print("outcome distribution:", dict(Counter(e.get("outcome") or "none" for e in entries).most_common()))
    routes = Counter((e.get("system"), e.get("pattern"), e.get("tier")) for e in entries)
    print(f"\ndistinct (system,pattern,tier) routes: {len(routes)}")
    print("top 5 routes:")
    for r, c in routes.most_common(5):
        print(f"   {c:3d}x  {r[0]} > {r[1]} @ {r[2]}")
    # Majority-class baseline: what you'd get by always guessing the most common route
    mc = routes.most_common(1)[0]
    print(f"\nMAJORITY-CLASS BASELINE: always answer {mc[0]} "
          f"=> {100*mc[1]/len(entries):.1f}% route accuracy with no retrieval at all")

    for min_sim in (0.15, 0.10, 0.05):
        run(entries, min_sim, False, "no class filter")
    for min_sim in (0.15, 0.05):
        run(entries, min_sim, True, "class-filtered (per protocol)")


if __name__ == "__main__":
    main()
