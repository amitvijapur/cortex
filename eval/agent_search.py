#!/usr/bin/env python3
"""agent_search — lexical retrieval over the agent roster.

WHY THIS EXISTS
    Cortex has 267 installed agents but routes to ~16 of them. The failure is not that
    the roster is bad, it is that selection is driven by what the model can recall from a
    long in-context list. Recall favours whatever was named in cortex.md, which is why
    named agents are over-represented 4.1x among agents actually used. A retrieval step
    replaces recall with search: the model asks for candidates and gets a handful.

WHY BM25F RATHER THAN THE NAIVE OVERLAP SCORE
    The prior scorer (eval/build_retrieval_set.py:score) is unweighted set overlap. Every
    term counts the same, so `Specialist` in "Grading Specialist" matches `Specialist` in
    "Xiaohongshu Specialist" as strongly as a genuinely discriminating term would. The
    roster is full of these: 30+ agents end in Engineer, Specialist, Strategist, Analyst,
    Developer or Architect. Those tokens carry almost no information about WHICH agent
    fits, yet the naive score lets them dominate a 2-token query.

    IDF fixes exactly this class of error. A term appearing in 40 of 267 agents scores an
    order of magnitude below a term appearing in 2. It is the single highest-leverage
    change available without embeddings.

FIELDS
    Indexing only the frontmatter description throws away the majority of what each agent
    file says about itself. Agent bodies state scope, domain vocabulary, and explicit
    refusals ("does not write firmware"). Those are retrieval signal. Fields are weighted
    rather than concatenated so a name match still outranks an incidental body mention.

STDLIB ONLY
    No embeddings, no network. This is lexical retrieval done properly, which is a real
    ceiling — see the evaluation notes in eval_retrieval.py for where that ceiling bites.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
AGENTS_DIR = CLAUDE_DIR / "agents"

SKIP_STEMS = {"readme", "index", "contributing", "contributing_zh-cn", "license",
              "security", "code_of_conduct", "changelog"}

# Structural words plus roster-wide role suffixes. The role suffixes are NOT dropped from
# the index (IDF already discounts them and they still break ties); they are dropped only
# from being treated as strong evidence on their own.
STOP = set("""
a an the and or but if then than that this these those of for to in on at by with without
from into over under via using use uses used is are was were be been being am do does did
it its it's as not no nor so such can could should would may might must will shall have
has had you your our their his her they them we i me my
""".split())

TOKEN_RE = re.compile(r"[a-z0-9]+")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.M)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

# Field weights. Name dominates because an exact role-name query should win outright, but
# not so much that a 1-of-2 token name collision beats a genuine description match.
#
# BODY IS DELIBERATELY EXCLUDED, against the intuition that more text retrieves better.
# Measured on dev, adding agent bodies costs 3 points of R@5 at every blend weight tried
# (see the field sweep in eval_retrieval.py). Bodies are 3-6k characters of persona prose,
# worked examples and code blocks; they roughly triple the vocabulary of every document
# while adding almost no discriminating terms, so they mostly manufacture weak matches for
# agents that happen to mention a common word. The useful part of a body is a small,
# curated slice — which is what ENRICHED_FIELD_WEIGHTS below exploits, and the difference
# between curated and indiscriminate content is the main finding of the evaluation.
FIELD_WEIGHTS = {"name": 8.0, "description": 3.0}

# Used when descriptions have been augmented with mined capability terms.
ENRICHED_FIELD_WEIGHTS = {"name": 8.0, "description": 3.0, "capabilities": 2.0}

K1 = 1.2
B = 0.55
# A bigram that survives both query and document is much stronger evidence than its parts.
BIGRAM_BOOST = 2.2


def stem(tok: str) -> str:
    """Conservative suffix stripper.

    Deliberately timid. Aggressive stemming collapses distinct roster roles (`Architect`
    vs `Architecture` is fine to merge; `Analyst` vs `Analytics` is not obviously fine).
    Only endings that are near-always inflectional are touched, and only when a
    reasonable stem remains.
    """
    if len(tok) <= 3:
        return tok
    for suf, repl, minlen in (("ies", "y", 4), ("sses", "ss", 5), ("ing", "", 6),
                              ("ers", "er", 5), ("ions", "ion", 6), ("es", "", 5),
                              ("s", "", 4)):
        if tok.endswith(suf) and len(tok) >= minlen:
            cand = tok[: len(tok) - len(suf)] + repl
            if len(cand) >= 3:
                return cand
    return tok


def tokenize(text: str, keep_stop: bool = False) -> list[str]:
    toks = TOKEN_RE.findall((text or "").lower())
    if not keep_stop:
        toks = [t for t in toks if t not in STOP]
    return [stem(t) for t in toks]


def bigrams(toks: list[str]) -> list[str]:
    return [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


@dataclass
class Agent:
    name: str
    division: str
    path: str
    description: str
    fields: dict[str, str] = field(default_factory=dict)
    tf: Counter = field(default_factory=Counter)
    weighted_len: float = 0.0


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse the leading YAML block. Handles the multi-line quoted descriptions the
    roster actually contains, which a naive line-by-line partition truncates."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head, body = text[3:end], text[end + 4:]
    meta, key, buf = {}, None, []

    def flush():
        if key:
            meta[key] = " ".join(buf).strip().strip("\"'")

    for line in head.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            flush()
            key, buf = m.group(1).strip().lower(), [m.group(2)]
        elif key and line.strip():
            buf.append(line.strip())
    flush()
    return meta, body


def load_roster(agents_dir: Path = AGENTS_DIR,
                overrides: dict[str, str] | None = None,
                body_chars: int = 6000,
                include_docs: bool = False) -> dict[str, Agent]:
    """Read every agent definition into a field-separated document.

    CORPUS HYGIENE — this is not incidental, it was worth ~16 points of recall.
    `rglob("*.md")` over the roster directory does not return 267 agents. It returns 292
    files, 43 of which are READMEs, contributor guides, strategy playbooks
    ("phase-3-build.md") and worked examples ("workflow-landing-page.md"). Titling their
    filenames turns them into plausible-looking agents with long, keyword-dense bodies,
    and they then win queries outright. The rule applied here is that an agent is a file
    that declares itself one with a `name:` in frontmatter; documentation does not.

    `integrations/` additionally holds per-tool variants that reuse a canonical agent's
    name verbatim (`backend-architect-with-memory.md` declares `name: Backend
    Architect`). Keyed by name, a plain sorted walk lets the variant silently replace the
    canonical definition. Canonical copies win here.

    `overrides` maps agent name -> replacement description, used by the description
    ablation so rewritten descriptions can be measured WITHOUT editing the roster files.
    """
    roster: dict[str, Agent] = {}
    for path in sorted(agents_dir.rglob("*.md")):
        if path.stem.lower() in SKIP_STEMS:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        meta, body = _split_frontmatter(text)
        name = (meta.get("name") or "").strip()
        if not name:
            # Documentation, not an agent definition. `include_docs` reproduces the
            # original contaminated corpus so its cost can be measured rather than
            # asserted; nothing but the ablation should pass it.
            if not include_docs:
                continue
            name = path.stem.replace("-", " ").title()
        if name in roster and "integrations" in Path(roster[name].path).parts:
            pass       # incumbent is a variant; the canonical copy below replaces it
        elif name in roster:
            continue   # canonical already loaded; ignore variants
        desc = meta.get("description", "")
        if overrides and name in overrides:
            desc = overrides[name]
        # `vibe` is a one-line self-summary present on many agents; it is description-grade.
        if meta.get("vibe"):
            desc = f"{desc} {meta['vibe']}".strip()
        body = body[:body_chars]
        roster[name] = Agent(
            name=name,
            division=path.parent.name if path.parent != agents_dir else "root",
            path=str(path),
            description=desc,
            fields={
                "name": name,
                "description": desc,
                "headings": " ".join(HEADING_RE.findall(body)),
                "emphasis": " ".join(BOLD_RE.findall(body)),
                "body": body,
                "division": path.parent.name.replace("-", " "),
            },
        )
    return roster


def enrich_descriptions(roster: dict[str, Agent], per_agent: int = 25) -> dict[str, Agent]:
    """Mine each agent's own body for its most distinctive terms and expose them as a
    `capabilities` field.

    This is the honest, non-leaky test of "would better descriptions beat a better
    ranker". Hand-writing descriptions for the agents that happen to be dev golds would
    just be fitting 25 examples with extra steps. Instead the same mechanical rule runs
    over all agents, with no reference to the dev set, to any gold label, or to any query:
    score every body term by tf-idf against the roster, keep the top terms that the
    name and description do not already contain.

    That models what a good description does — surface the distinctive vocabulary a person
    would actually search for — while isolating it from the confound of simply indexing
    more text, which is measured separately and shown to hurt. If curated terms help where
    raw bodies hurt, the difference is attributable to curation rather than volume.
    """
    df: Counter = Counter()
    bodies: dict[str, Counter] = {}
    for name, ag in roster.items():
        tf = Counter(tokenize(ag.fields.get("body", "")))
        bodies[name] = tf
        for t in tf:
            df[t] += 1
    N = len(roster) or 1

    for name, ag in roster.items():
        seen = set(tokenize(ag.fields["name"])) | set(tokenize(ag.fields["description"]))
        ranked = sorted(
            ((tf * math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)), t)
             for t, tf in bodies[name].items()
             if t not in seen and df[t] < N * 0.25 and len(t) > 2),
            reverse=True)
        ag.fields["capabilities"] = " ".join(t for _, t in ranked[:per_agent])
    return roster


class AgentIndex:
    """BM25F over the roster. Small enough (245 docs) to build per process in ~100ms."""

    def __init__(self, roster: dict[str, Agent], use_bigrams: bool = True,
                 fields: dict[str, float] | None = None):
        self.roster = roster
        self.use_bigrams = use_bigrams
        self.weights = dict(fields or FIELD_WEIGHTS)
        self.df: Counter = Counter()
        self.N = len(roster)

        for ag in roster.values():
            tf: Counter = Counter()
            wlen = 0.0
            for fname, w in self.weights.items():
                toks = tokenize(ag.fields.get(fname, ""))
                if not toks:
                    continue
                units = toks + (bigrams(toks) if use_bigrams else [])
                for t in units:
                    tf[t] += w * (BIGRAM_BOOST if "_" in t else 1.0)
                wlen += w * len(toks)
            ag.tf, ag.weighted_len = tf, wlen
            for t in tf:
                self.df[t] += 1

        lens = [a.weighted_len for a in roster.values()] or [1.0]
        self.avgdl = sum(lens) / len(lens)
        self._idf = {t: math.log(1 + (self.N - d + 0.5) / (d + 0.5))
                     for t, d in self.df.items()}

    def idf(self, term: str) -> float:
        # Unseen term: maximal IDF is wrong (it contributes nothing), so return 0.
        return self._idf.get(term, 0.0)

    def _units(self, text: str) -> Counter:
        toks = tokenize(text)
        if not toks:
            return Counter()
        q: Counter = Counter()
        for t in toks + (bigrams(toks) if self.use_bigrams else []):
            q[t] += BIGRAM_BOOST if "_" in t else 1.0
        return q

    def _bm25(self, q: Counter) -> dict[str, float]:
        out: dict[str, float] = {}
        for name, ag in self.roster.items():
            s = 0.0
            for term, qw in q.items():
                tf = ag.tf.get(term)
                if not tf:
                    continue
                denom = tf + K1 * (1 - B + B * ag.weighted_len / self.avgdl)
                s += qw * self.idf(term) * (tf * (K1 + 1)) / denom
            if s > 0:
                out[name] = s
        return out

    def _overlap(self, task: str, label: str, top_k: int) -> list[tuple[str, float]]:
        """Weighted token overlap — the naive baseline, and the DEFAULT ranker.

        It is the default because it won. Scored on a sealed 26-pair split that the BM25F
        work never saw, overlap beat BM25F at every K:

            R@1  42.3% vs 30.8%    R@3  73.1% vs 53.8%
            R@5  76.9% vs 65.4%    R@10 80.8% vs 80.8%

        On the 25-pair dev set BM25F had looked better by two queries at R@5 (p=0.50).
        That reversed on held-out data, which is what a blend weight and field weights
        swept over 25 examples will do. The tuning is kept below rather than deleted, so
        it can be re-tested once agent descriptions are rewritten — the ceiling analysis
        says vocabulary, not ranking, is what actually caps this.
        """
        ql = {t for t in tokenize(label)}
        qt = {t for t in tokenize(task)}
        if not ql and not qt:
            return []
        scored = []
        for name, ag in self.roster.items():
            nm = set(tokenize(ag.name))
            ds = set(tokenize(ag.description))
            q = ql or qt
            s = (0.70 * len(q & nm) / len(q)
                 + 0.20 * len(q & ds) / len(q)
                 + 0.10 * (len(qt & nm) / len(nm) if nm else 0.0))
            if s > 0:
                scored.append((name, s))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:top_k]

    def search(self, task: str, label: str = "", top_k: int = 10,
               label_w: float = 0.8, ranker: str = "overlap") -> list[tuple[str, float]]:
        """Score the label and the task as SEPARATE channels, then blend.

        Concatenating them into one bag of words is the obvious approach and it is wrong
        here, for a reason visible in the data rather than in theory. In the dev set 25
        queries come from only 17 distinct tasks, and five of those tasks each map to two
        or three *different* correct agents — one "deep research" task is correctly
        answered by Data Engineer, Sports Perception Scientist and Real-Time Feedback
        Designer depending on which leg of the fan-out is being routed. For those queries
        the task text is provably non-discriminating: identical input, different correct
        output. Only the label separates them.

        Under a concatenated query the ~15-token task contributes several times the mass
        of the ~2-token label, so the non-discriminating channel dominates the
        discriminating one and every leg of a fan-out collapses to the same answer.
        Scoring the channels independently and normalising each to its own maximum puts
        them on a comparable footing regardless of length, so the label decides the role
        and the task supplies domain context to break ties.

        `label_w` is the blend. It is deliberately reported as a plateau rather than a
        tuned optimum — see the sweep in eval_retrieval.py.
        """
        if ranker == "overlap":
            return self._overlap(task, label, top_k)

        if label_w is None:
            # Single-channel control: label and task concatenated into one bag of words,
            # which is the conventional thing to do and the thing the split replaces.
            merged = self._bm25(self._units(f"{label} {label} {task}"))
            return sorted(merged.items(), key=lambda x: (-x[1], x[0]))[:top_k]

        s_label = self._bm25(self._units(label)) if label.strip() else {}
        s_task = self._bm25(self._units(task)) if task.strip() else {}
        if not s_label and not s_task:
            return []
        # Normalise each channel to its own best score. Without this the blend weight is
        # entangled with query length and stops meaning anything.
        ml = max(s_label.values()) if s_label else 1.0
        mt = max(s_task.values()) if s_task else 1.0
        wl = label_w if s_label else 0.0
        wt = (1 - label_w) if s_task else 0.0
        if wl + wt == 0:
            return []
        wl, wt = wl / (wl + wt), wt / (wl + wt)

        scored = []
        for name in self.roster:
            s = wl * (s_label.get(name, 0.0) / ml) + wt * (s_task.get(name, 0.0) / mt)
            if s > 0:
                # Rescale to a roughly BM25-like magnitude so the abstain thresholds stay
                # interpretable as "how good is the best match" rather than a bare ratio.
                scored.append((name, s * max(ml, mt)))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:top_k]


# --------------------------------------------------------------------------------------
# Abstain
# --------------------------------------------------------------------------------------

@dataclass
class SearchResult:
    candidates: list[tuple[str, float]]
    abstain: bool
    reason: str
    confidence: float


# The absolute floor is scale-dependent: BM25 scores run to ~10, overlap is bounded by 1.
# A single constant silently abstains on everything under the other ranker, so the default
# is chosen per ranker rather than baked in.
ABSTAIN_FLOOR = {"overlap": 0.30, "bm25f": 6.0}


def search_with_abstain(index: AgentIndex, task: str, label: str = "", top_k: int = 5,
                        min_score: float | None = None, min_margin: float = 0.12,
                        **kw) -> SearchResult:  # noqa: D417
    """Return candidates, or abstain.

    Two independent failure shapes need catching, so there are two gates:

      1. NOTHING MATCHED (absolute). Every candidate scores low. The query vocabulary
         simply is not in the roster — a genuine capability gap. Thresholding on the raw
         top score catches this.
      2. EVERYTHING MATCHED EQUALLY (relative). Scores are high but flat, which is the
         signature of a query made of common roster vocabulary ("research the platform")
         where a dozen agents are equally defensible. Returning the arbitrary winner of a
         near-tie is precisely the confident-wrong failure this system exists to prevent.
         Thresholding on the top1-vs-top2 relative margin catches this.

    Abstaining still returns the candidates. The caller should show them as weak
    suggestions rather than a routing decision, because "here are three maybes, none
    convincing" is honest and useful, whereas naming one is neither.

    CALIBRATION HONESTY. On the dev set the margin gate does all of the work and the
    absolute gate never fires — every value of `min_score` from 0 to 6 gives identical
    behaviour, because no dev query is pure gibberish. `min_score` is retained as a guard
    for the case dev does not contain (a query with no real relationship to any agent),
    but it is UNVALIDATED and should not be trusted until such queries are observed.

    `min_margin` trades coverage for precision smoothly rather than peaking, which is the
    good case: 0.08 -> 19/25 answered at 84%, 0.12 -> 18/25 at 83%, 0.18 -> 15/25 at 87%.
    0.12 is a middle setting, not an optimum, and is meant to be turned as a dial.
    """
    ranked = index.search(task, label, top_k=max(top_k, 5), **kw)
    if not ranked:
        return SearchResult([], True, "no lexical overlap with any agent", 0.0)
    top = ranked[0][1]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = (top - second) / top if top > 0 else 0.0
    if min_score is None:
        min_score = ABSTAIN_FLOOR.get(kw.get("ranker", "overlap"), 0.30)
    if top < min_score:
        return SearchResult(ranked[:top_k], True,
                            f"best score {top:.1f} below {min_score}", margin)
    if margin < min_margin:
        return SearchResult(ranked[:top_k], True,
                            f"top-2 margin {margin:.0%} below {min_margin:.0%} "
                            f"({ranked[0][0]} vs {ranked[1][0]})", margin)
    return SearchResult(ranked[:top_k], False, "", margin)


# --------------------------------------------------------------------------------------
# CLI  —  `python3 eval/agent_search.py "<task text>"`
# Intended to be wired up as `cortex agents search`; bin/cortex is owned elsewhere, so
# this stays a standalone entry point. See docs/proposals for the wiring proposal.
# --------------------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Search the agent roster for candidates.")
    ap.add_argument("task", help="task text to route")
    ap.add_argument("--label", default="", help="role name the model had in mind")
    ap.add_argument("-k", "--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-abstain", action="store_true")
    args = ap.parse_args()

    index = AgentIndex(load_roster())
    res = search_with_abstain(index, args.task, args.label, top_k=args.top)

    if args.json:
        print(json.dumps({
            "abstain": res.abstain and not args.no_abstain,
            "reason": res.reason,
            "confidence": round(res.confidence, 3),
            "candidates": [
                {"name": n, "score": round(s, 2),
                 "division": index.roster[n].division,
                 "description": index.roster[n].description[:200]}
                for n, s in res.candidates],
        }, indent=2))
        return

    if not args.label.strip():
        # Measured, not guessed: with a role hint the retriever finds the gold in the top
        # 5 for 18/25 dev queries; on task text alone it manages 7/17 distinct tasks.
        # Callers who have a role in mind should say so.
        print("note: no --label given. Task-only retrieval is substantially weaker "
              "(7/17 vs 18/25 on dev).\n      Pass the role you have in mind, e.g. "
              "--label 'security reviewer'.\n")

    if res.abstain and not args.no_abstain:
        print(f"NO CONFIDENT MATCH — {res.reason}")
        print("Treat these as weak suggestions, not a routing decision:\n")
    for i, (name, score) in enumerate(res.candidates, 1):
        ag = index.roster[name]
        print(f"{i}. {name}  [{ag.division}]  {score:.1f}")
        print(f"   {ag.description[:160]}")


if __name__ == "__main__":
    main()
