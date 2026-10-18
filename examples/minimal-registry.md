# Minimal registry for a first task

You can try Cortex with your coding agent's normal file and shell tools. No orchestrator, specialist pool or hosted adviser is required.

This is a **registry excerpt**, not a complete `cortex.md`. Read your installed framework first. Back it up, then review a merge of the two sections below into its `Workflow Registry` and `Decision Shortcuts`. Preserve the routing protocol, effort calibration and history instructions. Remove placeholder workflow entries and shortcuts that assume tools you cannot call. Preserve any real workflows you already configured.

For a custom state root, also replace the framework's default `~/.claude/bin/cortex` references with the executable in your selected root. The [first-run guide](../docs/first-run.md) explains how to keep paths consistent.

```markdown
## Workflow Registry

### Direct
**Installed:** Yes, after confirming the current host exposes file and shell tools.
**Strengths:** A bounded task completed with the host's normal tools.
**Best for:** Focused reviews and reversible edits with clear acceptance checks.

| Pattern | Use When |
| --- | --- |
| bounded-review | Inspect a specified area, report evidence and leave files unchanged. |
| bounded-edit | Make a small, reversible change and run its focused checks. |
| plan-and-verify | Write a plan, implement in steps and perform a separate review pass. |

These are descriptions of how the agent works, not installed commands. Use only
available tools. Keep permissions and existing project instructions in force.
If an independent verifier is needed but unavailable, state that limit.

## Decision Shortcuts

| Task Type | Default Route | Tier |
| --- | --- | --- |
| Focused review with a clear scope | Direct > bounded-review | L2 |
| Small reversible edit with an acceptance check | Direct > bounded-edit | L2 |
| Change needing a plan and separate verification | Direct > plan-and-verify | L3, only when a concrete risk warrants it |
```

L1 trivia still skips the full protocol. The L3 row is conditional, not a new default. Add other systems only after confirming they are callable in your session. A registry does not install tools or authorize paid calls.
