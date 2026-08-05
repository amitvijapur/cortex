#!/usr/bin/env python3
"""worksheet_md — render the retrieval candidates as a markdown labelling sheet.

The JSON worksheet is the machine artifact; this is the human one. Labelling 79 rows in
raw JSON is miserable and error-prone, and a labelling surface nobody wants to open is a
labelling surface that stays empty.

Rows are grouped by what decision they actually need, because the three groups take very
different amounts of thought:

  CONFIRM   a plausible proposal exists. Usually a yes/no.
  JUDGE     a proposal exists but is weak, often a single-word collision. Needs a look.
  GAP       nothing in the roster plausibly covers the label. Either a real capability
            gap, or the label was never an agent name to begin with (task decompositions
            like "synthesis" or "Stat 1" are common in the log).
"""
import argparse
import json
import os
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
DEFAULT_OUT = (Path.home() / "Desktop/Personal/Obsidian Folders/2nd Brain"
               / "Claude Code/Cortex/Retrieval Worksheet.md")


def row(c):
    task = (c["task"] or "")[:110]
    lines = [f"**`{c['invented_label']}`**",
             f"- route task: {task}"]
    if c["proposed_agent"]:
        lines.append(f"- proposed: **{c['proposed_agent']}** "
                     f"({c['match_score']:.2f}, division `{c['division']}`)")
        if c["runners_up"]:
            lines.append(f"- runners-up: {', '.join(c['runners_up'])}")
    else:
        lines.append(f"- proposed: none (best score {c['match_score']:.2f})")
    lines.append("- **your answer →** ")
    return "\n".join(lines)


def review_doc(cands):
    """Render for review rather than for labelling, once answers exist.

    Grouped by what the answer implies, because each group leads somewhere different:
    a real agent is a discovery failure, a gap justifies adding an agent, and a
    non-agent justifies splitting the overloaded `agent` field.
    """
    agent = [c for c in cands if c["label"] not in ("none", "not-an-agent")]
    gap = [c for c in cands if c["label"] == "none"]
    nota = [c for c in cands if c["label"] == "not-an-agent"]

    def block(c):
        who = " *(yours)*" if c.get("labelled_by") == "amit" else ""
        flag = f"\n  - ⚠️ {c['review_flag']}" if c.get("review_flag") else ""
        why = f" — {c['label_reason']}" if c.get("label_reason") else ""
        return (f"- **`{c['invented_label']}`** → **{c['label']}**{who}{why}\n"
                f"  - task: {(c['task'] or '')[:100]}{flag}")

    out = ["---", "tags: [cortex, worksheet]", "status: labelled-pending-review", "---", "",
           "# Retrieval Worksheet — for review", "",
           "Answers filled in by Claude except where marked *(yours)*. "
           "Correct anything wrong by editing the bold answer in place.", "",
           f"**{len(cands)} rows**: {len(agent)} map to a real agent, {len(gap)} are gaps, "
           f"{len(nota)} were never agent names.", "", "---", "",
           "## 1. Maps to a real agent — these are discovery failures", "",
           "The roster already covered the job and the route invented a name instead. "
           "This is the evidence that agent discovery is broken rather than the roster "
           "being too small.", ""]
    out += [block(c) for c in agent]
    out += ["", "---", "", "## 2. Genuine gaps — nothing in the roster fits", "",
            "These justify *adding* agents. Note how they cluster: computer vision and "
            "real-time perception, hardware and edge silicon, and formal science.", ""]
    out += [block(c) for c in gap]
    out += ["", "---", "", "## 3. Never agent names", "",
            "Fan-out legs, filenames, tool calls and topology slots recorded in the "
            "`agent` field. This is the evidence for splitting that field into "
            "specialist / executor / legs.", ""]
    out += [block(c) for c in nota]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(CLAUDE_DIR / "eval" / "retrieval-candidates.json"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    d = json.loads(Path(args.src).read_text())
    cands = d["candidates"]
    if all(c.get("label") for c in cands):
        Path(args.out).write_text("\n".join(review_doc(cands)))
        print(f"review sheet: {args.out}")
        return
    confirm = sorted([c for c in cands if c["proposed_agent"] and c["match_score"] >= 0.5],
                     key=lambda c: -c["match_score"])
    judge = sorted([c for c in cands if c["proposed_agent"] and c["match_score"] < 0.5],
                   key=lambda c: -c["match_score"])
    gap = sorted([c for c in cands if not c["proposed_agent"]], key=lambda c: -c["match_score"])

    out = [
        "---", "tags: [cortex, worksheet]", "status: unlabelled", "---", "",
        "# Retrieval Worksheet", "",
        "Labelling surface for the Phase 4 agent-retrieval evaluation set. "
        "Generated from the routing log, **not** ground truth.", "",
        "## How to fill this in", "",
        "For each entry, write after `your answer →` one of:", "",
        "- **an agent name** — the roster agent that should have been used",
        "- **`none`** — no existing agent fits, this is a real gap",
        "- **`not-an-agent`** — the label was a task decomposition or an execution note, "
        "never a specialist (common: `synthesis`, `Stat 1`, `wave 2`)", "",
        "Skip anything you are unsure about. A blank is more useful than a guess, "
        "because a wrong label silently corrupts every measurement built on it later.", "",
        "> Do not split this into train/test yourself. The split gets drawn after "
        "labelling, and the held-out half must stay unread while agent descriptions are "
        "being rewritten, or the evaluation measures memorisation instead of retrieval.", "",
        f"**{len(cands)} rows**: {len(confirm)} to confirm, {len(judge)} to judge, "
        f"{len(gap)} likely gaps or non-agents.", "",
        "---", "",
        "## A. Confirm (a plausible match exists)", "",
        "Fastest section. Mostly yes/no.", "",
    ]
    out += [row(c) + "\n" for c in confirm]
    out += ["---", "", "## B. Judge (weak match, look properly)", "",
            "The matcher scores by word overlap, so these are often single-word "
            "collisions rather than real matches. `Dependency Auditor` matched Paid Media "
            "**Auditor**; the right answer was probably Application Security Engineer.", ""]
    out += [row(c) + "\n" for c in judge]
    out += ["---", "", "## C. No match found", "",
            "Either a genuine capability gap, or never an agent name. Both answers are "
            "useful: gaps justify adding an agent, non-agents justify splitting the "
            "`agent` field so decompositions stop being recorded as specialists.", ""]
    out += [row(c) + "\n" for c in gap]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out))
    print(f"{len(cands)} rows: {len(confirm)} confirm, {len(judge)} judge, {len(gap)} gap")
    print(f"worksheet: {args.out}")


if __name__ == "__main__":
    main()
