---
name: cortex-learn
description: Detect routing patterns in the Cortex log and surface candidate Decision Shortcuts for cortex.md. Use when the user asks for routing patterns, wants to tune cortex defaults, or says "/cortex-learn".
trigger: /cortex-learn
---

# /cortex-learn

Run pattern detection on `~/.claude/cortex-log.jsonl`. Surface groups of routing decisions that repeated ≥3 times as candidate Decision Shortcuts for cortex.md.

## When to invoke

- User types `/cortex-learn` explicitly
- User asks "what patterns is cortex seeing"
- User asks "are there routes I should codify"
- User says "tune cortex based on usage"
- Session-start check (via `cortex learn --check`) surfaced a pending pattern

## What to do

### Step 1 — Run pattern detection

```bash
python3 ~/.claude/bin/cortex learn
```

Optional:
- `--threshold N` — change minimum count (default 3)
- `--check` — terse one-liner for session-start use (no review flow)
- `--no-proposals` — skip writing markdown proposal files

### Step 2 — Review the proposals

For each detected pattern, the tool writes a markdown proposal file with frontmatter status `pending`. The user should:

1. Read each proposal
2. Decide: approve, modify, or reject
3. Edit the proposal frontmatter to reflect the decision
4. If approved: add the candidate shortcut to `cortex.md` → Decision Shortcuts table
5. If rejected: write a one-line reason in the Notes section

### Step 3 — Update cortex.md (only if approved)

Take the candidate shortcut row and merge it into the Decision Shortcuts table in `cortex.md`. Don't overwrite existing rows that already cover the same case.

## Do NOT

- Do not auto-apply patterns to cortex.md — Amit must approve each one
- Do not delete proposal files even after approval; they're the audit trail
- Do not skip the `--no-proposals` flag if the user explicitly asks for stats only
