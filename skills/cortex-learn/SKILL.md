---
name: cortex-learn
description: Detect routing patterns in the Cortex log and surface candidate Decision Shortcuts for cortex.md. Use when the user asks for routing patterns, wants to tune cortex defaults, or says "/cortex-learn".
trigger: /cortex-learn
---

# /cortex-learn

Run pattern detection on the active state's `cortex-log.jsonl`. Surface groups of routing decisions that repeated ≥3 times as candidate Decision Shortcuts for cortex.md.

## When to invoke

- User types `/cortex-learn` explicitly
- User asks "what patterns is cortex seeing"
- User asks "are there routes I should codify"
- User says "tune cortex based on usage"
- Session-start check (via `cortex learn --check`) surfaced a pending pattern

## What to do

### Step 1 — Run pattern detection

Resolve the state directory from `CORTEX_HOME`, then `CLAUDE_DIR`, then
`$HOME/.claude`, matching the CLI and installer. Keep a custom override exported
in the agent's environment. Use that directory's `cortex.md` for registry edits.

```bash
cortex_state_dir="${CORTEX_HOME:-${CLAUDE_DIR:-$HOME/.claude}}"
python3 "$cortex_state_dir/bin/cortex" learn
```

Optional:
- `--threshold N` — change minimum count (default 3)
- `--check` — terse one-liner for session-start use (no review flow)
- `--no-proposals` — skip writing markdown proposal files

### Step 2 — Review the proposals

For each detected pattern, the tool writes a markdown proposal file with frontmatter status `pending`. The user should:

1. Read each proposal
2. Decide: approve, modify, or reject
3. If rejected: persist `status: rejected` in that exact proposal's YAML frontmatter and write a one-line reason in Notes. A checkbox or a chat acknowledgement alone does not persist the decision.
4. If approved (including an approved modification): add the agreed shortcut to `cortex.md` → Decision Shortcuts table, then persist `status: approved` in the proposal. Keep `class`, `system`, and `pattern` as the original detection identity; put approved changes in the candidate row and Notes.
5. Read back the edited file before confirming the decision. If the write fails, report that it was not saved. Do not claim suppression based only on the user's reply.

Approved, rejected and superseded tuples are excluded from ordinary future suggestions, even if their counts grow. `cortex learn --include-actioned` explicitly includes them again. Do not promise automatic reconsideration on growth. With `--no-proposals`, report only; there is no proposal decision to persist unless the user requests one.

### Step 3 — Update cortex.md (only if approved)

Take the candidate shortcut row and merge it into the Decision Shortcuts table in `cortex.md`. Don't overwrite existing rows that already cover the same case.

## Do NOT

- Do not auto-apply patterns to cortex.md — Amit must approve each one
- Do not delete proposal files even after approval; they're the audit trail
- Do not skip the `--no-proposals` flag if the user explicitly asks for stats only
