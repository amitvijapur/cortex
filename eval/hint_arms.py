#!/usr/bin/env python3
"""Every proposed `hint` retriever, scored on one denominator.

Three retrieval changes have now been proposed for this log: a tuned BM25F ranker, semantic
embeddings, and a graph layer. The first two lost. The pattern each time was a better
scoring function offered for a problem whose bottleneck was somewhere else, and each time
the comparison was made against whichever baseline flattered it. This script exists so that
cannot happen again: every arm replays the same entries against the same prior pool and is
scored on the same metric.

**The query-time constraint, which decides more than the metrics do.** At the moment `hint`
runs, the protocol has produced a task string, a class, and a project. It has not produced a
route, a tier, or an agent, because those are what the hint is for. So an edge defined by
route, tier or agent cannot be traversed from the query. It exists only in hindsight. The
graph proposal's headline affordance, "two tasks that both routed to Backend Architect @ L3
are related", describes an edge that is unavailable at exactly the moment it would be used.
The graph arm here is therefore the strongest version that is actually legal: it traverses
the edges a cold query has (class, project), then expands one further hop through agent to
reach priors no direct edge reaches.

**What the score means.** `correct` = the arm surfaced the route the entry actually received.
That is agreement with history, not correctness. History is salience-driven, as the eval
README says, so a rising number here could mean better retrieval or merely more conformity.
Nothing in this file tests route quality; the only artifact that could is the frozen replay
set, and it is unlabelled.

Read-only. Run: python3 eval/hint_arms.py
"""
import json
import math
import os
from collections import Counter, defaultdict
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
LOG_PATH = CLAUDE_DIR / "cortex-log.jsonl"

# Imported rather than reimplemented, for the same reason route_eval.py imports
# parse_route: a private copy of the tokenizer is free to drift from the shipped one,
# and then the "current behaviour" arm stops measuring current behaviour.
_cli = SourceFileLoader("cortex_cli", str(REPO / "bin" / "cortex")).load_module()
tokens = _cli.tokens

TOP_N = 5
MIN_POOL = 3


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


def route_of(e):
    return (e.get("system"), e.get("pattern"), e.get("tier"))


# ---------------------------------------------------------------------------
# Arms. Each takes (query_entry, chronologically prior pool) and returns a ranked
# list of prior entries, longest-first by relevance, capped at TOP_N.
# ---------------------------------------------------------------------------

def arm_jaccard(q, pool, floor=0.15):
    """Shipped behaviour: class filter, Jaccard over task text, hard similarity gate."""
    pool = [e for e in pool if e.get("class") == q.get("class")]
    qt = tokens(q.get("task", ""))
    scored = [(jaccard(qt, tokens(e.get("task", ""))), e) for e in pool]
    scored = [(s, e) for s, e in scored if s >= floor]
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:TOP_N]]


def arm_jaccard_open(q, pool):
    """Same scoring, gate dropped to 0.05. Tests whether the gate or the score is the fault."""
    return arm_jaccard(q, pool, floor=0.05)


def arm_recency(q, pool):
    """No scoring at all: same class, most recent N. The baseline that should go first."""
    return [e for e in pool if e.get("class") == q.get("class")][-TOP_N:][::-1]


def arm_recency_project(q, pool):
    """Same class, same project preferred, most recent N. Falls back to class-only."""
    same = [e for e in pool if e.get("class") == q.get("class")]
    proj = [e for e in same if e.get("project") == q.get("project")]
    ranked = proj[::-1] + [e for e in same[::-1] if e not in proj]
    return ranked[:TOP_N]


def arm_shape_oracle(q, pool):
    """Upper bound on shape retrieval. Matches the query's OWN tier_reason against prior
    tier_reasons. Cheats: tier_reason is written when the route is logged, so it does not
    exist at query time. Its only job is to answer whether shape retrieval would work AT
    ALL, before anyone builds the feature extractor that would make it legal."""
    pool = [e for e in pool if e.get("class") == q.get("class")]
    qt = tokens(q.get("tier_reason", ""))
    if not qt:
        return []
    scored = [(jaccard(qt, tokens(e.get("tier_reason", ""))), e) for e in pool]
    scored.sort(key=lambda x: -x[0])
    return [e for s, e in scored[:TOP_N] if s > 0]


def arm_shape_crossfield(q, pool):
    """Legal version of the above: query TASK text against prior TIER_REASON text. Tests
    whether shape vocabulary is recoverable from how the task was worded."""
    pool = [e for e in pool if e.get("class") == q.get("class")]
    qt = tokens(q.get("task", ""))
    scored = [(jaccard(qt, tokens(e.get("tier_reason", ""))), e) for e in pool]
    scored.sort(key=lambda x: -x[0])
    return [e for s, e in scored[:TOP_N] if s > 0]


def arm_graph_2hop(q, pool):
    """The graph arm, restricted to edges a cold query actually has.

    Hop 1: priors sharing class or project with the query.
    Hop 2: from those, priors sharing an agent with a hop-1 node. This is the only
    expansion in the whole proposal that reaches nodes no direct attribute match reaches.
    Nodes are scored by weighted edge count, hop-2 discounted, then the highest-scoring
    priors are returned.
    """
    idx = list(range(len(pool)))
    by_agent = defaultdict(list)
    for i in idx:
        if pool[i].get("agent"):
            by_agent[pool[i]["agent"]].append(i)

    score = defaultdict(float)
    hop1 = set()
    for i in idx:
        e = pool[i]
        s = 0.0
        if e.get("class") == q.get("class"):
            s += 1.0
        if e.get("project") == q.get("project"):
            s += 1.5          # project is the sharper of the two query-time edges
        if s:
            score[i] += s
            hop1.add(i)

    for i in list(hop1):
        ag = pool[i].get("agent")
        if not ag:
            continue
        for j in by_agent[ag]:
            if j not in hop1:
                score[j] += 0.5 * score[i] / 2.5    # discounted, normalised by max hop-1

    # Recency breaks ties, otherwise the vote is decided by arbitrary log order.
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], -kv[0]))
    return [pool[i] for i, _ in ranked[:TOP_N]]


ARMS = {
    "jaccard >=0.15 (shipped)": arm_jaccard,
    "jaccard >=0.05": arm_jaccard_open,
    "recency, class": arm_recency,
    "recency, class+project": arm_recency_project,
    "shape crossfield (legal)": arm_shape_crossfield,
    "shape oracle (cheats)": arm_shape_oracle,
    "graph 2-hop (query-legal)": arm_graph_2hop,
}


def mcnemar_exact(b, c):
    """Two-sided exact binomial test on discordant pairs. No scipy dependency."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main():
    rows = [json.loads(line) for line in open(LOG_PATH) if line.strip()]
    entries = [r for r in rows if r.get("task")]
    entries.sort(key=lambda r: r.get("ts", ""))

    queries = [i for i in range(len(entries)) if i >= MIN_POOL]
    # 'findable' = at least one chronologically prior entry carries the same route. Where
    # none does, no retriever can succeed, so scoring over all queries dilutes every arm
    # by the same constant and hides which one is actually recovering the reachable cases.
    findable = set()
    for i in queries:
        if any(route_of(p) == route_of(entries[i]) for p in entries[:i]):
            findable.add(i)

    print(f"log: {LOG_PATH}")
    print(f"entries: {len(entries)}   queries (pool >= {MIN_POOL}): {len(queries)}   "
          f"findable: {len(findable)} ({100 * len(findable) / len(queries):.1f}%)")
    print()
    print("'findable' = a prior entry with the same route exists. The oracle ceiling.")
    print("Correct = the route this entry actually got. Agreement with history, not quality.")
    print()

    hits = {}
    print(f"  {'arm':<28} {'fires':>7} {'top-1':>7} {'top-5':>7} {'top-5 of findable':>19}")
    print(f"  {'-' * 28} {'-' * 7} {'-' * 7} {'-' * 7} {'-' * 19}")

    for name, fn in ARMS.items():
        fired = t1 = t5 = t5f = 0
        per_query = {}
        for i in queries:
            q, pool = entries[i], entries[:i]
            got = fn(q, pool)
            if got:
                fired += 1
            truth = route_of(q)
            routes = [route_of(e) for e in got]
            ok5 = truth in routes
            if routes and routes[0] == truth:
                t1 += 1
            if ok5:
                t5 += 1
                if i in findable:
                    t5f += 1
            per_query[i] = ok5
        hits[name] = per_query
        nf = len(findable)
        print(f"  {name:<28} {100 * fired / len(queries):6.1f}% {100 * t1 / len(queries):6.1f}%"
              f" {100 * t5 / len(queries):6.1f}% {t5f:8d}/{nf:<3d} = {100 * t5f / nf:5.1f}%")

    print()
    print("=" * 78)
    print("PAIRED COMPARISON — graph against the best arm that needs no graph")
    print("=" * 78)

    no_graph = {k: v for k, v in hits.items() if not k.startswith("graph")
                and "oracle" not in k}
    best = max(no_graph, key=lambda k: sum(no_graph[k].values()))
    graph = hits["graph 2-hop (query-legal)"]

    b = sum(1 for i in queries if no_graph[best][i] and not graph[i])
    c = sum(1 for i in queries if graph[i] and not no_graph[best][i])
    p = mcnemar_exact(b, c)

    print(f"  best no-graph arm: {best}")
    print(f"  discordant pairs:  no-graph only {b}, graph only {c}")
    print(f"  McNemar exact two-sided p = {p:.4f}")
    print()
    print("  Pre-registered bar, fixed before the graph arm was written and carried over")
    print("  from the MLX decision at the same sample size: the graph must recover at")
    print("  least 5 cases the best no-graph arm misses, net. Anything smaller is not")
    print(f"  distinguishable from noise here. Net recovery: {c - b:+d}.")
    print()
    verdict = "CLEARS" if (c - b) >= 5 and p < 0.05 else "DOES NOT CLEAR"
    print(f"  Verdict: the graph arm {verdict} the bar.")

    label_sensitivity(entries, queries)


def label_sensitivity(entries, queries):
    """Why the recency baseline is quoted at several different numbers.

    The MLX decision recorded 23.8% for 'recency, same class, no scoring' at n=130 and
    treated it as the pre-registered bar for Stage 1. That figure was computed ad hoc and
    never committed, and it does not reproduce here: the same window gives 19.2% for the
    literal reading, 20.8% deduplicating by route, and 25.4% if the label is loosened to
    system+pattern. The grid below is printed so the next person does not have to rederive
    it, and so the bar lives in code rather than in prose.

    The lesson is the eval README's own, arrived at from a new direction: a number that is
    not produced by a committed script is not a baseline, because nothing stops it drifting
    or being remembered generously.
    """
    print()
    print("=" * 78)
    print("LABEL SENSITIVITY — why 'the recency baseline' has three different values")
    print("=" * 78)

    full = lambda e: (e.get("system"), e.get("pattern"), e.get("tier"))
    syspat = lambda e: (e.get("system"), e.get("pattern"))

    def variant(key, dedup):
        hit = 0
        for i in queries:
            pool = [e for e in entries[:i] if e.get("class") == entries[i].get("class")]
            seen = []
            for e in reversed(pool):
                r = key(e)
                if dedup and r in seen:
                    continue
                seen.append(r)
                if len(seen) >= TOP_N:
                    break
            if key(entries[i]) in seen:
                hit += 1
        return 100 * hit / len(queries)

    print(f"  {'label':<18} {'top-5, recent entries':>23} {'top-5, distinct routes':>24}")
    print(f"  {'-' * 18} {'-' * 23} {'-' * 24}")
    for name, key in (("full route", full), ("system+pattern", syspat)):
        print(f"  {name:<18} {variant(key, False):22.1f}% {variant(key, True):23.1f}%")
    print()
    print("  Deduplicating by route is the variant shipped: it scores marginally better and")
    print("  produces five distinct suggestions rather than five rows that may collapse to")
    print("  two. The margin is under the 5-case bar, so that is a design preference with a")
    print("  measurement attached, not a claimed improvement.")


if __name__ == "__main__":
    main()
