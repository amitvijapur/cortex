#!/usr/bin/env python3
"""eval_retrieval — measure agent retrieval against the labelled dev set.

WHAT IS MEASURED
    recall@K: of N queries, the fraction where the gold agent appears in the top K.
    Numerator and denominator are printed for every cell so no number is unattributable.

UNCERTAINTY
    N=25. A single query is worth 4 percentage points, so a 4pp difference between two
    systems is one query and means nothing. Every rate is reported with a Wilson 95%
    interval (correct for proportions near 0 and 1, unlike the normal approximation), and
    system-vs-system deltas use a paired bootstrap over queries plus an exact McNemar
    test on the discordant pairs, because the two systems see the SAME queries and a
    paired test is far more sensitive than comparing two independent intervals.

ABLATION DESIGN
    The task asks which matters more, the ranker or the descriptions. Those are separable:

      baseline   naive overlap, name + frontmatter description       (prior art)
      ranker     BM25F,          name + frontmatter description       (ranker changed only)
      +content   BM25F,          name + description + body + headings (content changed only)

    baseline -> ranker isolates the retrieval algorithm, since the indexed text is
    identical. ranker -> +content isolates description/content quality, since the
    algorithm is identical. Attributing the total gain without this decomposition would
    be guesswork.

LEAKAGE DISCIPLINE
    Only retrieval-dev.json is read. The sealed test split is never opened by this file
    and must not be, since tuning against it would destroy its only purpose.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_search import (ENRICHED_FIELD_WEIGHTS, FIELD_WEIGHTS,  # noqa: E402
                          AgentIndex, enrich_descriptions, load_roster,
                          search_with_abstain, tokenize)

DEV = Path.home() / ".claude" / "eval" / "retrieval-dev.json"
KS = (1, 3, 5, 10)
STOP_NAIVE = set("the a an and or for of to in on with using via".split())


# ----------------------------------------------------------------------------- baseline
def naive_norm(s: str) -> list[str]:
    import re
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()


def naive_score(label: str, task: str, agent_name: str, desc: str) -> float:
    """Verbatim port of build_retrieval_set.score, so the comparison is to the real prior
    art and not to a strawman rewritten from memory."""
    q = set(naive_norm(label)) - STOP_NAIVE
    if not q:
        return 0.0
    name = set(naive_norm(agent_name)) - STOP_NAIVE
    d = set(naive_norm(desc)) - STOP_NAIVE
    task_q = set(naive_norm(task)) - STOP_NAIVE
    return (0.70 * len(q & name) / len(q)
            + 0.20 * len(q & d) / len(q)
            + 0.10 * len(task_q & name) / (len(name) or 1))


def naive_rank(roster, task, label, top_k=10):
    scored = [(n, naive_score(label, task, n, a.description)) for n, a in roster.items()]
    scored = [(n, s) for n, s in scored if s > 0]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:top_k]


# -------------------------------------------------------------------------- statistics
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Used instead of k/n +- z*sqrt(p(1-p)/n) because at N=25 the
    normal approximation produces intervals that run past 0 and 1 and understates
    uncertainty at the extremes, which is exactly where several of these cells land."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact binomial p on discordant pairs. With N=25 the chi-square
    approximation is not usable; the exact test is cheap and correct."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired_bootstrap(hits_a: list[bool], hits_b: list[bool], iters=20000, seed=7):
    """Resample QUERIES (not systems) so both systems are always evaluated on the same
    resampled set. Returns the CI on the delta and the fraction of resamples where B
    does not beat A."""
    rng = random.Random(seed)
    n = len(hits_a)
    deltas = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(sum(hits_b[i] for i in idx) / n - sum(hits_a[i] for i in idx) / n)
    deltas.sort()
    lo, hi = deltas[int(0.025 * iters)], deltas[int(0.975 * iters)]
    return lo, hi, sum(1 for d in deltas if d <= 0) / iters


# ------------------------------------------------------------------------------ systems
def build_systems(overrides=None):
    """Each system is (name, rank_fn(task,label,k) -> [(agent, score)]).

    The ladder is deliberately ordered so each rung changes ONE thing:
      baseline   -> corpus    : same scorer, junk documents removed
      corpus     -> BM25F     : same text, IDF + field weighting + bigrams
      BM25F      -> 2-channel : same index, label and task scored separately
      2-channel  -> enriched  : same scorer, descriptions auto-augmented from bodies
      (aside)    raw body     : the "just index more text" hypothesis, measured not assumed
    """
    roster_clean = load_roster(overrides=overrides)
    roster_dirty = load_roster(overrides=overrides, include_docs=True)

    idx = AgentIndex(load_roster(overrides=overrides), fields=FIELD_WEIGHTS)
    idx_enr = AgentIndex(enrich_descriptions(load_roster(overrides=overrides)),
                         fields=ENRICHED_FIELD_WEIGHTS)
    idx_body = AgentIndex(load_roster(overrides=overrides),
                          fields={"name": 8.0, "description": 3.0, "body": 1.0})

    return {
        "0 baseline (naive overlap, raw corpus)":
            lambda t, l, k: naive_rank(roster_dirty, t, l, k),
        "1 baseline + corpus hygiene":
            lambda t, l, k: naive_rank(roster_clean, t, l, k),
        "2 BM25F, single query channel":
            lambda t, l, k: idx.search(t, l, top_k=k, label_w=None, ranker="bm25f"),
        "3 BM25F, label/task split  [MAIN]":
            lambda t, l, k: idx.search(t, l, top_k=k, ranker="bm25f"),
        "4 (3) + auto-enriched descriptions":
            lambda t, l, k: idx_enr.search(t, l, top_k=k, ranker="bm25f"),
        "5 (3) + raw agent bodies indexed":
            lambda t, l, k: idx_body.search(t, l, top_k=k, ranker="bm25f"),
    }, idx


def hits_at(rank_fn, pairs, k):
    out = []
    for p in pairs:
        ranked = rank_fn(p["task"], p.get("invented_label", ""), max(KS))
        names = [n for n, _ in ranked[:k]]
        out.append(p["label"] in names)
    return out


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k:2d}/{n:2d} = {k/n:5.1%}  [{lo:.0%}, {hi:.0%}]"


# --------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default=str(DEV))
    ap.add_argument("--overrides", default="", help="JSON {agent: description} to swap in")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    dev = json.loads(Path(args.dev).read_text())
    pairs = [p for p in dev["pairs"] if p.get("label") and p["label"] != "none"]
    n = len(pairs)

    overrides = json.loads(Path(args.overrides).read_text()) if args.overrides else None
    systems, idx = build_systems(overrides)

    # Sanity: every gold label must exist in the roster, else recall is capped silently.
    missing = sorted({p["label"] for p in pairs} - set(idx.roster))
    print(f"dev pairs: {n}   roster: {len(idx.roster)} agents")
    if missing:
        print(f"!! gold labels absent from roster (recall capped): {missing}")
    print()

    results = {}
    print(f"{'system':<38}" + "".join(f"{'R@'+str(k):>26}" for k in KS))
    print("-" * (38 + 26 * len(KS)))
    for sname, fn in systems.items():
        row, cells = [], {}
        for k in KS:
            h = hits_at(fn, pairs, k)
            cells[k] = h
            row.append(f"{sum(h):2d}/{n} {sum(h)/n:5.1%} [{wilson(sum(h),n)[0]:.0%},"
                       f"{wilson(sum(h),n)[1]:.0%}]".rjust(26))
        results[sname] = cells
        print(f"{sname:<38}" + "".join(row))

    # ------------------------------------------------------------- reachability ceiling
    # The most important number in this file. If the gold agent's indexed text shares no
    # content term with the query, no lexical retriever can ever rank it — not with a
    # better scorer, not with more tuning. That caps recall independently of the ranker,
    # and it is what decides whether further ranker work is worth doing at all.
    print("\nlexical reachability ceiling (can ANY lexical retriever reach the gold?)")
    print("-" * 92)
    roster = idx.roster
    enr = enrich_descriptions(load_roster(overrides=overrides))
    reach_l = reach_lt = reach_enr = 0
    unreachable = []
    for p in pairs:
        g = roster.get(p["label"])
        if not g:
            continue
        ql = set(tokenize(p.get("invented_label", "")))
        qt = set(tokenize(p["task"]))
        idxable = set(tokenize(g.fields["name"])) | set(tokenize(g.fields["description"]))
        if ql & idxable:
            reach_l += 1
        else:
            unreachable.append((p["label"], p.get("invented_label", "")))
        if (ql | qt) & idxable:
            reach_lt += 1
        if ql & (idxable | set(tokenize(enr[p["label"]].fields["capabilities"]))):
            reach_enr += 1
    print(f"  reachable from LABEL alone      {fmt(reach_l, n)}   <- ceiling on label-led R@K")
    print(f"  reachable from LABEL+TASK       {fmt(reach_lt, n)}")
    print(f"  reachable after auto-enrichment {fmt(reach_enr, n)}")
    print("  structurally unreachable: "
          + "; ".join(f"{g} <- {l!r}" for g, l in unreachable))

    # ---------------------------------------------------------------- paired comparisons
    names = list(systems)
    print("\npaired comparisons at R@5 (same 25 queries, so a paired test applies)")
    print("-" * 92)
    for a, b in ((names[0], names[1]), (names[1], names[3]), (names[2], names[3]),
                 (names[3], names[4]), (names[3], names[5])):
        ha, hb = results[a][5], results[b][5]
        b_only = sum(1 for x, y in zip(ha, hb) if not x and y)
        a_only = sum(1 for x, y in zip(ha, hb) if x and not y)
        lo, hi, p_boot = paired_bootstrap(ha, hb)
        p_mc = mcnemar_exact(a_only, b_only)
        print(f"  {b}\n    vs {a}")
        print(f"    delta {sum(hb)/n - sum(ha)/n:+.1%}  bootstrap 95% CI "
              f"[{lo:+.0%}, {hi:+.0%}]   fixed by B only: {b_only}, broken by B: {a_only}"
              f"   McNemar exact p={p_mc:.3f}")

    # ------------------------------------------------------------------ label provenance
    print("\nby label provenance (does who labelled it change the difficulty?)")
    print("-" * 92)
    groups = {}
    for p in pairs:
        g = "amit" if str(p.get("labelled_by", "")).startswith("amit") else "claude"
        groups.setdefault(g, []).append(p)
    for sname in [names[1], names[3]]:
        print(f"  {sname}")
        for g, gp in sorted(groups.items()):
            h = hits_at(systems[sname], gp, 5)
            print(f"    {g:<8} R@5 {fmt(sum(h), len(gp))}")

    # A provenance difference could be an artefact of query shape rather than labeller
    # judgement, so measure the shape directly.
    print("\n  query shape by provenance (the likely confound)")
    for g, gp in sorted(groups.items()):
        lab_len = statistics.mean(len(tokenize(p.get("invented_label", ""))) for p in gp)
        exact = sum(1 for p in gp
                    if p.get("invented_label", "").lower().replace("-", " ")
                    in {p["label"].lower()})
        prop = sum(1 for p in gp if p.get("proposed_agent") == p["label"])
        print(f"    {g:<8} n={len(gp):2d}  mean label tokens {lab_len:.1f}  "
              f"label==gold (modulo case/hyphen): {exact}  "
              f"baseline's own proposal was already right: {prop}")

    # ------------------------------------------------------------------------- abstain
    print("\nabstain behaviour (BM25F, label/task split [MAIN])")
    print("-" * 92)
    fired = kept_hit = kept_miss = abst_hit = abst_miss = 0
    for p in pairs:
        r = search_with_abstain(idx, p["task"], p.get("invented_label", ""),
                                top_k=5, ranker="bm25f")
        hit = p["label"] in [x for x, _ in r.candidates]
        if r.abstain:
            fired += 1
            abst_hit, abst_miss = abst_hit + hit, abst_miss + (not hit)
        else:
            kept_hit, kept_miss = kept_hit + hit, kept_miss + (not hit)
    answered = kept_hit + kept_miss
    print(f"  answered {answered}/{n}   precision@5-contains-gold on answered: "
          f"{fmt(kept_hit, answered) if answered else 'n/a'}")
    print(f"  abstained {fired}/{n}   of those, gold was in top-5 anyway: "
          f"{abst_hit}/{fired} (cost of abstaining)")
    print(f"  confident-and-wrong (the failure abstain exists to prevent): "
          f"{kept_miss}/{n} = {kept_miss/n:.0%}"
          f"   vs {sum(not h for h in results[names[3]][5])}/{n} without abstain")

    # ------------------------------------------------------------------ per-query detail
    print("\nper-query (BM25F, label/task split, top-5); '.' = gold retrieved, X = miss")
    print("-" * 92)
    for p in pairs:
        ranked = systems[names[3]](p["task"], p.get("invented_label", ""), 10)
        top = [x for x, _ in ranked[:5]]
        rank = top.index(p["label"]) + 1 if p["label"] in top else 0
        mark = "." if rank else "X"
        print(f"  {mark} rank={rank or '-':<2} gold={p['label'][:30]:<32} "
              f"label={p.get('invented_label','')[:22]:<24} got={top[0][:28] if top else '-'}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"n": n, "recall": {s: {k: sum(v) for k, v in c.items()}
                                for s, c in results.items()}}, indent=2))


if __name__ == "__main__":
    main()
