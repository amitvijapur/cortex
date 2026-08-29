#!/usr/bin/env python3
"""Separates 'nobody used this' from 'nothing could ever route to this'.

Nineteen registry entries were moved out of the always-on `cortex.md` into
`cortex-registry-extended.md` on the evidence that the routing log never mentions them.
For most of them that inference is sound. For three it is not: Knowledge Work Plugins,
Claude Tag Plugins and Toolport had no Decision Shortcuts row even before the split, so
the routing protocol was never told they existed. Zero usage measures the routing table
there, not the tool, and retiring on that evidence would be retiring for a reason the
tool had no way to affect.

This script reports the two things separately for every entry:

  REACHABLE   does a Decision Shortcuts row in cortex.md point at it?
  USED        does any log row mention it, across system / pattern / agent / task /
              the two free-text reason fields?

Only the REACHABLE-and-unused cell is evidence about the tool. The unreachable rows need
a decision about the routing table first, and can be judged on usage only after they have
had a period of actually being reachable.

Aliases are hand-curated below rather than inferred. Nineteen entries is small enough that
precision beats automation, and a fuzzy match that quietly counts the word "data" as a use
of the `data` plugin would produce exactly the false confidence this file exists to avoid.

Read-only. Run: python3 eval/registry_reachability.py
"""
import json
import os
import re
import shutil
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
LOG_PATH = CLAUDE_DIR / "cortex-log.jsonl"
CORTEX_MD = CLAUDE_DIR / "cortex.md"
EXTENDED_MD = CLAUDE_DIR / "cortex-registry-extended.md"

# entry name -> terms that would appear in a log row or a shortcut row if it were used.
# Deliberately specific: generic words are excluded even where the tool uses them, because
# a false positive here reads as "this tool is earning its place" when it is not.
ALIASES = {
    "Adversarial Spec": ["adversarial-spec", "adversarial spec"],
    "ECC": ["ecc", "feature-dev", "pr-review-toolkit", "ralph-loop", "code-simplifier",
            "commit-commands", "security-guidance"],
    "Gitleaks": ["gitleaks"],
    "Agent Browser": ["agent-browser", "agent browser"],
    "Knowledge Work Plugins": ["knowledge-work", "knowledge work", "enterprise-search",
                               "data plugin", "legal plugin"],
    "Claude Tag Plugins": ["claude-tag", "claude tag", "jira", "linear", "salesforce",
                           "hubspot", "datadog", "grafana", "pagerduty", "snowflake",
                           "redshift", "confluence"],
    "Community Skill Packs": ["obsidian-skills", "claude-mem", "last30days",
                              "defending-code", "humanizer"],
    "Anthropic Financial Services": ["financial-analysis", "model-builder", "pitch-agent",
                                     "market-researcher", "earnings-reviewer",
                                     "meeting-prep-agent", "equity-research",
                                     "anthropic finance"],
    "Hyperframes": ["hyperframes"],
    "Tessl Skills": ["tessl"],
    "Native Claude Code Surface": ["teleport", "/schedule", "remote control", "agent sdk",
                                   "channels", "github actions"],
    # Graphify Rituals is a sub-entry of Graphify, not a separate system. It inherits
    # Graphify's reachability, so it is folded in rather than scored as its own row —
    # listing it separately would manufacture a fourth "unreachable" entry out of a
    # heading.
    "Graphify (+ Rituals)": ["graphify"],
    "Understand Anything": ["understand-anything", "/understand", "understand anything"],
    "Domain Models": ["kronos", "quantmind", "domain model"],
    "Toolport": ["toolport"],
    "Cloud MCPs": ["figma", "notion", "granola", "scholar gateway", "canva",
                   "google calendar", "cloud mcp"],
    "Design Systems Library": ["design-systems", "design.md", "awesome-design-md",
                               "design systems library"],
    "Chrome DevTools MCP": ["chrome devtools", "chrome-devtools", "lighthouse"],
}

# Fields a use would show up in. The two reason fields are included because a route can
# name a tool in its justification without it being the system of record.
FIELDS = ("system", "pattern", "agent", "task", "system_reason", "tier_reason")

# Third axis. The registry's own "Installed:" line is prose and drifts: it claimed the
# design-systems library sat at ~/Desktop/design-systems, which does not exist, and it
# claimed Understand Anything was Pending when the plugin has been installed since
# 2026-07-19. An unused tool that is not on disk tells you nothing about the tool either,
# so the claim is checked rather than believed. `None` means there is nothing cheap to
# check and the entry is reported as unverified rather than guessed at.
INSTALL_PATHS = {
    "Adversarial Spec": "~/.claude/plugins/cache/adversarial-spec",
    "ECC": "~/.claude/plugins/cache/claude-plugins-official",
    "Gitleaks": "cmd:gitleaks",
    "Agent Browser": "cmd:agent-browser",
    "Knowledge Work Plugins": "~/.claude/plugins/cache/knowledge-work-plugins",
    "Claude Tag Plugins": "~/.claude/plugins/cache/claude-tag-plugins",
    "Community Skill Packs": "~/.claude/skills/humanizer",
    "Anthropic Financial Services": "~/.claude/plugins/cache/claude-for-financial-services",
    "Hyperframes": "~/Desktop/tools/hyperframes",
    "Tessl Skills": None,
    "Native Claude Code Surface": None,
    "Graphify (+ Rituals)": "~/.claude/skills/graphify",
    "Understand Anything": "~/.claude/plugins/cache/understand-anything",
    "Domain Models": "~/.claude/bin/kronos",
    "Toolport": "cmd:toolport-gateway",
    "Cloud MCPs": None,
    "Design Systems Library": "~/Desktop/design-systems",
    "Chrome DevTools MCP": None,
}


def installed(spec):
    """Returns True, False, or None for 'nothing cheap to check'."""
    if spec is None:
        return None
    if spec.startswith("cmd:"):
        return shutil.which(spec[4:]) is not None
    return Path(spec).expanduser().exists()


def shortcuts_section():
    text = CORTEX_MD.read_text()
    m = re.search(r"^## Decision Shortcuts$(.*?)^---", text, re.M | re.S)
    return (m.group(1) if m else "").lower()


def main():
    rows = [json.loads(line) for line in open(LOG_PATH) if line.strip()]
    entries = [r for r in rows if r.get("task")]
    entries.sort(key=lambda r: r.get("ts", ""))
    shortcuts = shortcuts_section()

    print(f"log: {LOG_PATH}   entries: {len(entries)}")
    print(f"registry: {EXTENDED_MD.name}   entries checked: {len(ALIASES)}")
    print()
    print(f"  {'entry':<30} {'on disk':>8} {'reachable':>10} {'used':>6} "
          f"{'last seen':>12}  where")
    print(f"  {'-' * 30} {'-' * 8} {'-' * 10} {'-' * 6} {'-' * 12}  {'-' * 20}")

    buckets = {"reachable-unused": [], "unreachable-unused": [], "used": [],
               "not-installed": []}

    for name, terms in ALIASES.items():
        reachable = any(t in shortcuts for t in terms)
        on_disk = installed(INSTALL_PATHS.get(name))

        hits, where, last = 0, set(), ""
        for e in entries:
            matched = False
            for f in FIELDS:
                v = str(e.get(f) or "").lower()
                if any(t in v for t in terms):
                    where.add(f)
                    matched = True
            if matched:
                hits += 1
                last = e.get("ts", "")[:10]

        flag = "yes" if reachable else "NO"
        disk = {True: "yes", False: "NO", None: "?"}[on_disk]
        loc = ",".join(sorted(where)) if where else "-"
        print(f"  {name:<30} {disk:>8} {flag:>10} {hits:6d} {last or '-':>12}  {loc}")

        # Conditions are reported independently rather than as one bucket per entry.
        # Claude Tag Plugins is both unreachable and absent; collapsing it into whichever
        # test ran first would hide one of the two reasons its usage count is zero, and
        # both have to be fixed before that zero means anything.
        if hits:
            buckets["used"].append(name)
        else:
            if on_disk is False:
                buckets["not-installed"].append(name)
            if not reachable:
                buckets["unreachable-unused"].append(name)
            if reachable and on_disk is not False:
                buckets["reachable-unused"].append(name)

    print()
    print("=" * 78)
    print("HOW TO READ THIS")
    print("=" * 78)
    print(f"  used ({len(buckets['used'])}) — the log mentions these. Usage count is not")
    print("    value: a single mention in a reason field is not a working habit.")
    print()
    print(f"  reachable but unused ({len(buckets['reachable-unused'])}) — the only cell that")
    print("    is evidence ABOUT THE TOOL. The protocol knew about these and still never")
    print("    reached for them.")
    for n in buckets["reachable-unused"]:
        print(f"      - {n}")
    print()
    print(f"  unreachable and unused ({len(buckets['unreachable-unused'])}) — no Decision")
    print("    Shortcuts row points here, so the router was never told they exist. Zero")
    print("    usage measures the routing table, not the tool. Decide whether to write the")
    print("    row; only judge usage after they have been reachable for a while.")
    for n in buckets["unreachable-unused"]:
        print(f"      - {n}")
    print()
    print(f"  not on disk ({len(buckets['not-installed'])}) — the registry says installed or")
    print("    pending, and the path is not there. Unused is not a verdict on a tool that")
    print("    was never present to be used. Install it or drop the entry; do not retire it")
    print("    for a lack of use it never had the chance to accrue.")
    for n in buckets["not-installed"]:
        print(f"      - {n}  (checked: {INSTALL_PATHS[n]})")


if __name__ == "__main__":
    main()
