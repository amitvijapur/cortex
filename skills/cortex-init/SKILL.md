---
name: cortex-init
description: Set up Cortex by discovering the user's existing systems and generating a personalized Workflow Registry from them. Use when the user runs /cortex-init, says "set up cortex", "adopt my tools into cortex", "build my registry", or right after installing Cortex for the first time.
---

# cortex-init — adopt the user's existing stack into Cortex

Cortex is a routing **layer**. This skill wires it around whatever the user *already* runs, instead of imposing a fixed toolset. Their systems are preserved and tied together — nothing is replaced, and their `cortex.md` is never overwritten without a backup and their confirmation.

Run these steps in order.

## 1. Discover — deterministic scan

Run the scanner:

```bash
python3 ~/.claude/bin/cortex init
```

It writes `<state-dir>/cortex-inventory.json` and prints a summary. **Read the JSON.** It lists their agents (counted by division), skills, commands, MCP servers, hooks, plugins, detected other-agent config files (Cursor / Codex / Gemini / Aider / Windsurf), and relevant CLIs on PATH.

## 2. Interview — fill gaps, don't interrogate

Auto-accept the obvious; only ask what you genuinely cannot infer. Keep it to a handful of questions. Ask about:

- **Grouping:** large pools (e.g. "262 agents across 21 divisions") — one "Specialist Agents" pool, or break out a few they reach for often?
- **Category** for any MCP/tool you can't classify from its name (search? database? scraping? design? docs?).
- **Defaults per task class** — for `build`, `review`, `plan`, `research`, `debug`, `design`, which of *their* systems is the go-to? Offer a sensible guess and let them correct it.
- **Exclusions** — anything detected that they do *not* want Cortex to route to.

Use their answers, not assumptions.

## 3. Synthesize the registry

Write a **Workflow Registry** in the exact shape Cortex uses (mirror the `## Workflow Registry` section of the installed `cortex.md`). For each system / agent-group / skill-family / MCP:

- **Installed:** Yes
- **Strengths:** one line
- **Best for:** one line
- a small pattern table — `| Pattern | Use When |`

Then draft a **Decision Shortcuts** table (`task type → default route → tier`) from the defaults they gave you. **Ground every entry in what the scan actually found — never invent a tool they don't have.**

## 4. Merge — non-destructive, always

- If `~/.claude/cortex.md` does **not** exist yet: `install.sh` created it from the template. Replace its `## Workflow Registry` section with your synthesized one.
- If it **exists**:
  1. **Back it up first:**
     ```bash
     cp ~/.claude/cortex.md ~/.claude/cortex.md.bak-$(date +%Y%m%dT%H%M%S)
     ```
  2. Replace **only** the `## Workflow Registry` section (its heading up to the next `##`) and the `## Decision Shortcuts` table. **Preserve** their Routing Protocol, Effort Calibration, and Self-Learning Loop sections verbatim — those are the framework, not their tools.
  3. Show the user a **diff** of what changed and **confirm before writing.**

When unsure, write your synthesized registry to `~/.claude/cortex.md.generated` and ask them to merge by hand. Never clobber a hand-customized `cortex.md`.

## 5. Verify

```bash
python3 ~/.claude/bin/cortex doctor
```

Confirm the registry lines up with what's installed. Tell the user they can re-run `/cortex-init` (or `cortex init`) any time they add a tool.

## Principles

- **Adopt, don't impose** — their systems tied together, not a replacement stack.
- **Never overwrite without a backup + confirmation.**
- **Only route to things that actually exist** in the scan.
