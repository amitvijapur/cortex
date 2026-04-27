---
name: cortex-log
description: Show recent Cortex routing decisions with reasoning trail. Use when the user asks what routes have been picked, wants to audit recent routing decisions, or says "show cortex log" / "what did cortex do" / "/cortex-log".
trigger: /cortex-log
---

# /cortex-log

Show the last N Cortex routing decisions from `~/.claude/cortex-log.jsonl` with full reasoning.

## When to invoke

- User types `/cortex-log` explicitly
- User asks "what routes have I been using"
- User asks "what did cortex pick for X"
- User says "show me recent routing decisions"
- User says "audit my recent routes"

## What to do

Run the `cortex show` command and print its output verbatim. Nothing else.

```bash
python3 ~/.claude/bin/cortex show --last 20
```

Optional args:
- `--last N` — show last N routes instead of 20
- `--project <name>` — filter to a specific project

## What the user sees

Each entry shows:
- Timestamp, project, task classification
- The original task description
- The chosen route (`System > Pattern > Agent @ Tier`)
- The reasoning tags (why this tier, why this system) — or `(obvious route)` when no tags were recorded

If the log is empty, the command prints `cortex log is empty — no routes logged yet`.

## Do NOT

- Do not aggregate or summarize the output — the user wants per-decision visibility, not stats
- Do not filter out routes unless the user explicitly asks
- Do not add commentary unless the user asks a follow-up question
