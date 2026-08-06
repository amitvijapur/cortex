#!/usr/bin/env python3
"""build_retrieval_set — assemble a labelling-ready retrieval evaluation set.

WHAT THIS PRODUCES
    Candidate (task -> agent) pairs for evaluating agent retrieval, mined from the
    routing log. It produces a WORKSHEET, not a gold set. The pairs are proposals that
    need confirmation before anything is measured against them.

WHY NOT A GOLD SET
    Three reasons, all of which would invalidate naive use of this data:

    1. Selection bias. The pairs come from a system whose agent selection is known to be
       salience-driven rather than fitness-driven, so the observed choices are not a
       sample of correct answers. They are a sample of what was reachable.
    2. Leakage. If these same pairs are used both to rewrite agent descriptions and to
       evaluate retrieval over those descriptions, the evaluation measures memorisation.
       The split must therefore be drawn AFTER labelling, and the held-out half must not
       be looked at while descriptions are being edited.
    3. The interesting rows are the invented ones. Where a route names a role that does
       not exist in the roster while a real agent covers that job, that is evidence of a
       discovery failure, and the "correct" answer is a judgement call, not a fact
       recoverable from the log.

HARD NEGATIVES
    For each candidate, plausible-but-wrong agents are drawn from the same division.
    Random negatives make retrieval look better than it is, because distinguishing a
    security agent from a marketing agent is trivial. Same-division confusions are where
    retrieval actually fails.
"""
import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
AGENTS_DIR = CLAUDE_DIR / "agents"
LOG_PATH = CLAUDE_DIR / "cortex-log.jsonl"

# The agent field records several different concepts in one slot. These split it back
# into the individual role tokens a route named.
SPLIT_RE = re.compile(r"\s*(?:∥|\||\+|,|→|->|;)\s*")
# Execution-topology and decomposition noise, not specialist names.
NOISE = re.compile(r"^(?:executor|opus|sonnet|haiku|fable|codex|gemini|qc|reconciler|"
                   r"lens|judge|amit|claude|direct|n/?a|self)\b", re.I)
STOP = set("the a an and or for of to in on with using via".split())

# Agents from other registries (OMC plugin, built-ins). A route naming these is not an
# invented label needing a roster match; it is a different catalogue being used.
EXTERNAL = re.compile(r"^(?:oh-my-claudecode:|omc:|understand-anything:|vercel:|tessl_|tessl$|plugin_)|"
                      r"^(?:general-purpose|explore|plan|critic|verifier|planner|analyst|"
                      r"tracer|debugger|writer|designer|scientist)$", re.I)
# Trailing execution annotations: "(serial", "wave 2", "Stat 1", "lens".
TRAIL = re.compile(r"\s*(?:\(.*|\bwave\s*\d+|\bstat\s*\d+|\blens\b|\bpass\b|\d+)\s*$", re.I)


def clean_token(tok):
    """Strip execution annotations so a real agent name still matches the roster."""
    tok = re.sub(r"\(.*?\)", "", tok)          # balanced parens
    prev = None
    while prev != tok:                          # unbalanced "(serial" and trailing noise
        prev, tok = tok, TRAIL.sub("", tok).strip(" -–:·")
    return tok.strip()


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()


def load_roster():
    """Return {canonical_name: {division, description}} from the agent definitions."""
    roster = {}
    for path in AGENTS_DIR.rglob("*.md"):
        if path.stem.lower() in {"readme", "index", "contributing", "license"}:
            continue
        try:
            text = path.read_text(errors="ignore")[:4000]
        except OSError:
            continue
        name, desc = path.stem.replace("-", " ").title(), ""
        if text.startswith("---"):
            end = text.find("\n---", 3)
            for line in text[3:end if end > 0 else 2000].splitlines():
                k, _, v = line.partition(":")
                if k.strip().lower() == "name" and v.strip():
                    name = v.strip().strip("\"'")
                elif k.strip().lower() == "description" and v.strip():
                    desc = v.strip().strip("\"'")[:400]
        if name == path.stem.replace("-", " ").title() and "name:" not in text[:400]:
            continue   # documentation, not an agent: no frontmatter name to declare one
        division = path.parent.name if path.parent != AGENTS_DIR else "root"
        # integrations/ holds per-tool variants reusing a canonical agent's name verbatim;
        # keyed by name a plain walk lets the variant replace the real definition.
        if name in roster and "integrations" not in Path(roster[name]["path"]).parts:
            continue
        roster[name] = {"division": division, "description": desc, "path": str(path)}
    return roster


def score(label, task, agent_name, meta):
    """Match the invented LABEL against the agent name first, description second.

    Weighting matters here. Scoring the whole task against long descriptions lets
    keyword-dense agents win on incidental vocabulary, which is how `deep-research`
    matched a Weibo strategist on the first attempt. The label is the signal; the task
    is weak corroboration.
    """
    q = set(norm(label)) - STOP
    if not q:
        return 0.0
    name = set(norm(agent_name)) - STOP
    desc = set(norm(meta["description"])) - STOP
    task_q = set(norm(task)) - STOP
    name_hit = len(q & name) / len(q)
    desc_hit = len(q & desc) / len(q)
    task_hit = len(task_q & name) / (len(name) or 1)
    return 0.70 * name_hit + 0.20 * desc_hit + 0.10 * task_hit


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(CLAUDE_DIR / "eval" / "retrieval-candidates.json"))
    ap.add_argument("--negatives", type=int, default=4, help="hard negatives per candidate")
    args = ap.parse_args()

    roster = load_roster()
    by_division = defaultdict(list)
    for n, m in roster.items():
        by_division[m["division"]].append(n)
    canon = {n.lower(): n for n in roster}

    rows = [json.loads(l) for l in LOG_PATH.read_text().splitlines() if l.strip()]

    matched, invented, external = [], [], []
    for e in rows:
        task, raw = e.get("task", ""), (e.get("agent") or "")
        for tok in filter(None, (t.strip(" []()").strip() for t in SPLIT_RE.split(raw))):
            if not tok or NOISE.match(tok) or len(tok) < 3:
                continue
            clean = clean_token(tok)
            key = clean.lower()
            if not clean or len(clean) < 3:
                continue
            if key in canon:
                matched.append({"task": task, "token": clean, "resolved": canon[key]})
            elif EXTERNAL.match(clean):
                external.append({"task": task, "token": clean})
            else:
                invented.append({"task": task, "token": clean})

    # Candidates: an invented role name plus the roster agents that best cover it.
    # These are the discovery failures, and the ones worth a human decision.
    seen, candidates = set(), []
    for item in invented:
        sig = (item["task"][:60], item["token"].lower())
        if sig in seen:
            continue
        seen.add(sig)
        ranked = sorted(((score(item["token"], item["task"], n, m), n)
                         for n, m in roster.items()), reverse=True)[:3]
        confident = bool(ranked) and ranked[0][0] >= 0.34
        best = ranked[0][1] if ranked else None
        negs = ([n for n in by_division[roster[best]["division"]] if n != best][:args.negatives]
                if confident else [])
        candidates.append({
            "task": item["task"],
            "invented_label": item["token"],
            # None means no roster agent plausibly covers this label, which is a candidate
            # genuine capability gap rather than a discovery failure.
            "proposed_agent": best if confident else None,
            "match_score": round(ranked[0][0], 3) if ranked else 0.0,
            "runners_up": [n for _, n in ranked[1:]] if confident else [],
            "hard_negatives": negs,
            "division": roster[best]["division"] if confident else None,
            "label": None,          # <- to be filled in by Amit: confirm / reject / replace
            "split": None,          # <- assigned AFTER labelling, never before
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "_status": "UNLABELLED WORKSHEET — not a gold set. See module docstring.",
        "_next_step": "Set `label` on each row to the correct agent name, or 'none' if no "
                      "roster agent fits. Only then assign `split`, and do not read the "
                      "held-out half while editing agent descriptions.",
        "roster_size": len(roster),
        "log_rows": len(rows),
        "agent_tokens_matching_roster": len(matched),
        "agent_tokens_invented": len(invented),
        "agent_tokens_external_registry": len(external),
        "candidates": candidates,
    }, indent=2))

    print(f"roster: {len(roster)} agents across {len(by_division)} divisions")
    print(f"log:    {len(rows)} routes")
    print(f"tokens: {len(matched)} matched roster, {len(external)} other registries, "
          f"{len(invented)} invented")
    print(f"candidates written: {len(candidates)} (unlabelled)\n")
    for c in candidates[:12]:
        tgt = c['proposed_agent'] or "(no confident match — possible real gap)"
        print(f"  {c['invented_label'][:32]:<32} -> {tgt[:36]:<36} {c['match_score']:.2f}")
    if len(candidates) > 12:
        print(f"  ... and {len(candidates)-12} more")
    print(f"\nworksheet: {out}")


if __name__ == "__main__":
    main()
