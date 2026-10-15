# Codex command attribution

## Contract

New Cortex route and correction events record `host`, `host_source` and
`session_ref_source`. Codex's native thread reference is `CODEX_THREAD_ID`.
`CODEX_SESSION_ID` is not used as the transcript ID. Explicit `CORTEX_HOST` and
`CORTEX_SESSION_ID` overrides are recorded as such. Conflicting native host
environments remain unknown unless explicitly resolved. Process fallbacks remain
useful for local correction scoping, but do not establish transcript identity.

The optional reader accepts local Codex `event_msg` / `item_completed` /
`CommandExecution` records, including actual nested shell executions from the
orchestration tool. It does not execute or parse model-written orchestration code.

An accepted record must have:

- Exactly one valid `session_meta` record in the file, with an ID and creation time.
- A supported top-level source (`vscode`, `cli` or `exec`), without parent or fork metadata.
- A matching explicit event `thread_id`, nonempty turn/item IDs and valid start/end times after session creation.
- A completed execution with integer exit code zero.
- One literal supported Cortex command, without help flags, compound shell syntax,
  substitutions, wrappers or redirection. Quoted routing strings are supported.

Shell comment/glob/brace markers are conservatively rejected even inside quotes.
Abbreviated/repeated task options and options before `log-line` positionals are
not reconstructed. A rejected command is undercoverage, not evidence of non-use.

Events deduplicate by thread, turn and item ID. Conflicting execution copies are
discarded, including success/failure disagreements. Conflicting session metadata
also prevents attribution. Codex session keys are namespaced separately from Claude.

A route joins only through an exact native thread reference, compatible host,
task argument and timestamp. Explicit conflicting references never fall back to
another session. Old `ppid_*` references and missing references remain unresolved.
No historical log row is rewritten or relabelled.

## What this does not grade

As of 15 October, Claude command evidence also rejects printed/quoted command
mentions, unsupported shell scripts and failed or incomplete tool executions.
Only conservative literal invocations with a successful matching tool result
can anchor routes or satisfy hint checks. This deliberately reduces coverage
when execution cannot be established. Unattributed recorded outcomes carry
`unknown` provenance, not an absent-outcome label. See the synthetic regression
suite in `eval/test_claude_command_evidence.py`.

This version establishes command ownership and route anchors, not full-transcript
adherence or outcome quality. It excludes user/assistant prose, model-facing
response items, compacted histories, multiple-metadata files, subagents and forks.
Fork acceptance needs a separately verified schema, not assumptions about history.
Missing or unsupported records remain unknown. Reads never modify rollouts.

Codex routes contribute to the explicitly labelled anchor coverage report. They do
not enter the existing hint-compliance, outcome-observation, session-substantiveness
or effort denominators. A separate per-route `codex_command_evidence` field can
report an observed successful hint completed before the route logging command
started. Its absence is null, never a measured miss. Command success is not task
success, and no outcome is automatically inferred.
Codex commands also do not feed missing-declaration warnings, since the selected
log may not be the log the recorded command targeted.

## Run without writing reports

Codex scanning is opt-in; the default Claude-only command is unchanged.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 eval/score_adherence.py \
  --codex-sessions "$HOME/.codex/sessions" --dry-run --check
PYTHONDONTWRITEBYTECODE=1 python3 eval/derive_outcomes.py \
  --codex-sessions "$HOME/.codex/sessions" --dry-run --no-git
```

Point the option at another rollout root for archived sessions. Adapter diagnostics
report files scanned and exclusions. Source files and the routing log remain intact.
Without `--dry-run`, the existing explicit report-output behavior still applies.

## Validation, 29 September 2026

Tests use synthetic, public-safe fixtures for ownership, foreign/pre-creation
records, forks/subagents, duplicate conflicts, malformed tails, quoted pseudo-commands,
help-only invocations, overlapping hint/log execution, host collisions and unresolved
process references. Both report entry points exercise the same adapter.

The final read-only live snapshot contained 483 routes and 787 rollout files.
It found 516 supported Cortex commands, but anchor-attributed routes remained
75 before and after, all Claude. Of the route references, 279 were process-based,
141 were missing and 63 were other references. This demonstrates why command
availability alone cannot establish ownership. Counts belong to that live snapshot;
sessions continue changing. The new identity fields support prospective attribution,
not a claimed retrospective recovery or improvement in routing quality.

Both independent reviewers cleared the bounded implementation after adversarial
parser and duplicate-record checks. Eighteen adapter tests and sixteen identity
tests pass, along with the CLI, runtime, evaluation, hint, Jev and installer
regression suites. The default-skipped intake integration tests were separately
run against disposable copies. The live adherence gate still fails its outcome
coverage floor at 80.5% versus 85%; enabling this reader does not make it pass.

The eval-harness workflow separates these deterministic acceptance checks from
quality evaluation. No paid models, service changes, transcript rewrites or rollout
activation are required by this adapter.
