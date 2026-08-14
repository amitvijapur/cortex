#!/usr/bin/env python3
"""Does the routing log contain a graph worth traversing?

A graph layer over the routing history has been proposed three times, always on the same
three affordances: correction chains as labelled edges, agent co-occurrence in fan-outs,
and task similarity by shared route structure rather than shared words. Each is plausible.
This script counts the edges each one would actually get before anyone builds a traversal
over them.

Two things it checks that a density count alone would miss:

**The clique problem.** A graph whose edges mean "shares attribute value v" is a disjoint
union of cliques, one per value. Every node's 1-hop neighbourhood is its entire clique, so
2-hop traversal returns the same set. Traversal depth buys nothing over a GROUP BY. That is
a property of the construction, not of this dataset, so it cannot be fixed with more rows.
Only heterogeneous relations (task -[agent]- task -[project]- task) expand at 2 hops, and
that expansion is measured here rather than assumed.

**Density against informativeness.** Coarsening the label makes the graph denser and the
prediction weaker. `tier` connects nearly everything and is 61% predictable by always
guessing the mode, so its edges carry almost nothing a constant does not. The full route
is informative and nearly edgeless. A graph is only worth building where edges are dense
AND the free baseline is weak, so both columns are reported side by side.

Read-only. Run: python3 eval/graph_density.py
"""
import json
import os
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
LOG_PATH = CLAUDE_DIR / "cortex-log.jsonl"

# Relations a task-task graph could be built on. Each maps an entry to a hashable value;
# two tasks are joined when the value matches and is not None.
RELATIONS = {
    "route (sys+pat+tier)": lambda e: (e.get("system"), e.get("pattern"), e.get("tier")),
    "system+pattern": lambda e: (e.get("system"), e.get("pattern")),
    "system": lambda e: e.get("system"),
    "agent": lambda e: e.get("agent"),
    "project": lambda e: e.get("project"),
    "class": lambda e: e.get("class"),
    "tier": lambda e: e.get("tier"),
}


def load():
    rows = [json.loads(line) for line in open(LOG_PATH) if line.strip()]
    entries = [r for r in rows if r.get("task")]
    entries.sort(key=lambda r: r.get("ts", ""))
    return rows, entries


def rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def explicit_edges(rows):
    """Edges the log records directly, rather than ones we infer from shared attributes."""
    rule("EXPLICIT EDGES — relations the log actually records")

    redirect = [r for r in rows if r.get("redirect_from")]
    correction = [r for r in rows if r.get("user_correction")]
    corrected = [r for r in rows if r.get("outcome") == "corrected"]
    ref_linked = [r for r in rows if r.get("ref") or r.get("session_ref")]
    legs = [r for r in rows if r.get("legs")]

    print(f"  {len(rows)} log rows total\n")
    print("  Correction chains — the proposal's highest-value edge type:")
    print(f"    redirect_from set          {len(redirect):4d}")
    print(f"    user_correction set        {len(correction):4d}")
    print(f"    outcome == 'corrected'     {len(corrected):4d}")
    print(f"    distinct correction edges  {len(set(id(r) for r in redirect + correction)):4d}")
    print()
    print("  Fan-out co-occurrence — which specialists get used together:")
    print(f"    rows carrying `legs`       {len(legs):4d}")
    print()
    print(f"  Other explicit refs (ref / session_ref)  {len(ref_linked):4d}")

    if len(redirect) + len(correction) < 10:
        print()
        print("  A correction graph over single-digit edges is a list. Nothing to traverse.")
    if not legs:
        print("  A co-occurrence graph with zero `legs` rows has no edges at all.")


def implicit_edges(entries):
    """Task-task edges inferred from a shared attribute, per relation."""
    rule("IMPLICIT EDGES — task-task graph per relation, and what it costs to predict")

    n = len(entries)
    max_edges = n * (n - 1) // 2
    print(f"  {n} task-bearing entries, {max_edges} possible undirected pairs\n")
    print(f"  {'relation':<22} {'edges':>7} {'density':>8} {'isolated':>9} "
          f"{'mean deg':>9} {'free baseline':>14}")
    print(f"  {'-' * 22} {'-' * 7} {'-' * 8} {'-' * 9} {'-' * 9} {'-' * 14}")

    results = {}
    for name, key in RELATIONS.items():
        groups = defaultdict(list)
        for i, e in enumerate(entries):
            v = key(e)
            if v is not None and v != (None, None) and v != (None, None, None):
                groups[v].append(i)

        edges = sum(len(g) * (len(g) - 1) // 2 for g in groups.values())
        degree = {i: 0 for i in range(n)}
        for g in groups.values():
            for i in g:
                degree[i] = len(g) - 1
        isolated = sum(1 for d in degree.values() if d == 0)

        # Free baseline: predict the modal label seen so far, chronologically. This is what
        # you get with no graph, no retrieval, and no code beyond a Counter.
        hits = seen_n = 0
        seen = Counter()
        for i, e in enumerate(entries):
            v = key(e)
            if i >= 3:
                seen_n += 1
                if seen and seen.most_common(1)[0][0] == v:
                    hits += 1
            if v is not None:
                seen[v] += 1

        density = edges / max_edges if max_edges else 0
        base = 100 * hits / seen_n if seen_n else 0
        print(f"  {name:<22} {edges:7d} {density:7.1%} {isolated:6d}/{n:<3d}"
              f" {edges * 2 / n:9.1f} {base:13.1f}%")
        results[name] = {"edges": edges, "isolated": isolated, "baseline": base,
                         "groups": groups}

    print()
    print("  'free baseline' = always predict the most common value seen so far. A graph")
    print("  has to beat that column to justify existing, in the same row where its edge")
    print("  count is non-trivial. Read the two together, not separately.")
    return results


def clique_check(entries, results):
    """Verify computationally that single-attribute graphs gain nothing at 2 hops."""
    rule("THE CLIQUE PROBLEM — does traversal depth buy anything?")

    print("  For a graph joined on one shared attribute, 1-hop and 2-hop neighbourhoods are")
    print("  identical by construction. Measured rather than asserted:\n")
    print(f"  {'relation':<22} {'mean 1-hop':>11} {'mean 2-hop':>11} {'expansion':>10}")
    print(f"  {'-' * 22} {'-' * 11} {'-' * 11} {'-' * 10}")

    for name in ("route (sys+pat+tier)", "agent", "project", "class"):
        groups = results[name]["groups"]
        member_of = {}
        for v, g in groups.items():
            for i in g:
                member_of.setdefault(i, []).append(v)

        adj = defaultdict(set)
        for v, g in groups.items():
            for i in g:
                adj[i].update(x for x in g if x != i)

        one = two = counted = 0
        for i in range(len(entries)):
            h1 = adj[i]
            if not h1:
                continue
            h2 = set()
            for j in h1:
                h2 |= adj[j]
            h2 -= {i}
            one += len(h1)
            two += len(h2)
            counted += 1
        if counted:
            print(f"  {name:<22} {one / counted:11.1f} {two / counted:11.1f} "
                  f"{two / one if one else 0:9.2f}x")

    print()
    print("  An expansion of 1.00x means the second hop returned exactly the first hop's set.")
    print("  Where that holds, 'graph traversal' and 'GROUP BY attribute' are the same query.")
    print("  Values just under 1.00x are not leakage in the other direction: in a 2-clique")
    print("  the second hop reaches only the origin, which is then excluded, so pair-heavy")
    print("  relations score slightly below 1. No relation exceeds 1.00x, which is the point.")

    # Heterogeneous 2-hop: task -[agent]- task -[project]- task. This is the only version
    # of the proposal where depth is not decorative, so it gets measured on its own.
    print()
    print("  Heterogeneous 2-hop (the one construction where depth is real):")
    ag = defaultdict(set)
    pr = defaultdict(set)
    for i, e in enumerate(entries):
        if e.get("agent"):
            ag[e["agent"]].add(i)
        if e.get("project"):
            pr[e["project"]].add(i)

    adj_a, adj_p = defaultdict(set), defaultdict(set)
    for g in ag.values():
        for i in g:
            adj_a[i] |= g - {i}
    for g in pr.values():
        for i in g:
            adj_p[i] |= g - {i}

    one = two = counted = 0
    for i in range(len(entries)):
        h1 = adj_a[i]
        if not h1:
            continue
        h2 = set()
        for j in h1:
            h2 |= adj_p[j]
        h2 -= {i} | h1
        one += len(h1)
        two += len(h2)
        counted += 1
    if counted:
        print(f"    task -[agent]- task -[project]- task:  {one / counted:.1f} at 1 hop, "
              f"{two / counted:.1f} NEW nodes at 2 hops  (n={counted})")
        print("    These are reachable only by traversal. Whether they are USEFUL is a")
        print("    separate question, answered by eval/hint_arms.py, not by this script.")


def main():
    rows, entries = load()
    print(f"log: {LOG_PATH}")
    print(f"rows: {len(rows)}   task-bearing: {len(entries)}   "
          f"span: {entries[0].get('ts', '?')[:10]} to {entries[-1].get('ts', '?')[:10]}")

    explicit_edges(rows)
    results = implicit_edges(entries)
    clique_check(entries, results)

    rule("WHAT THIS DOES AND DOES NOT SETTLE")
    print("  Settled here: how many edges exist, and whether traversal depth is decorative.")
    print("  Not settled here: whether a graph retriever beats the no-graph baselines on")
    print("  the chronological replay. That needs the same denominator for every arm and")
    print("  lives in eval/hint_arms.py.")


if __name__ == "__main__":
    main()
