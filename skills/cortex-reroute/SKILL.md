---
name: cortex-reroute
description: Mark the last Cortex routing decision as corrected and record the route the user actually wanted. Use when the user says "reroute", "actually use X", "should've been Y", or types "/cortex-reroute".
trigger: /cortex-reroute
---

# /cortex-reroute

Flag the most recent entry in `~/.claude/cortex-log.jsonl` as `outcome=corrected` and record the route the user wanted instead. This is the highest-quality training signal for Phase 3 (similarity bias) when it activates.

## When to invoke

- User types `/cortex-reroute "<corrected route>"` explicitly
- User says "reroute" / "actually use X" / "we should've used Y" right after a routing line
- User says "the right route was..." / "should've been..." / "redo with..."
- Any clear post-hoc correction of the last logged route

## What to do

### Step 1 — Mark the last entry as corrected

```bash
python3 ~/.claude/bin/cortex reroute --to "<the route the user wanted>"
```

The CLI:
- Sets `outcome=corrected` on the last log entry
- Stores the user's preferred route in `user_correction`
- Prints the before → after delta

### Step 2 — Log the new route

If the user wants the corrected route to actually run now, log it as a fresh entry with `--redirect-from` so the two are linked:

```bash
python3 ~/.claude/bin/cortex log \
  --task "<same task as before>" \
  --class <class> \
  --system <new system> \
  --pattern <new pattern> \
  --agent "<new agent>" \
  --tier <new tier> \
  --tier-reason "<...>" \
  --system-reason "User redirected from <old route>" \
  --redirect-from "<old route>"
```

The `redirect_from` field links the corrected entry to the new one — Phase 3 uses this to learn "Cortex picked X, user wanted Y" deltas.

### Step 3 — Course-correct the work

Carry out the user's preferred route. Don't argue with the correction unless there's a safety reason — the correction signal is sacred.

## Quote format for the `--to` argument

```
<System> > <Pattern> [> <Agent>] @ L<n>  [optional bracketed tags]
```

## Do NOT

- Do not invoke this for routes that ran fine — only for explicit corrections
- Do not modify older log entries; this only touches the most recent
- Do not skip step 2 if the user wants the corrected route to run — without `--redirect-from`, the link between old and new is lost
- Do not push back on the correction — the user's choice wins
