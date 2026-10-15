# Skill availability and use

Installed files, session exposure, a skill read, an invocation and faithful
application are separate observations. Cache counts and duplicate names do not
prove exposure or non-use. Never retire a skill from absent route mentions alone.

`cortex skill-use` is an optional local evidence recorder, not an automatic hook
or an evaluator. It records the actual resolved SKILL.md path and SHA-256, the
exact route ID, current host/session provenance, timestamp and a reported stage.
Stages are `read`, `invoked` and `applied`. Record only what actually happened.
Reading a skill does not imply invoking or applying it. Application is a claim
that still requires independent review, not a success score.

```bash
python3 ~/.claude/bin/cortex skill-use --ref '<canonical route event ID>' \
  --skill '<path to actual SKILL.md>' --stage read
```

Use an exact route ID belonging to the current host, session and project. The
command rejects ambiguous or foreign references. Evidence is appended separately
to `$CORTEX_HOME/cortex-skill-evidence.jsonl` (default `~/.claude`), leaving route
and outcome history unchanged. No skill body, prompt, tool arguments, outputs or
credentials are stored. Resolved paths are local metadata and may be private;
do not upload the stream or path inventories to public services.

All records explicitly say `self_reported`. Nothing is automatically inferred
from cache presence, exposure or successful shell execution. Missing evidence is
unknown, not failure or non-use. Existing historical usage cannot be recovered
by enabling this command. Turn/item-level host observation and independent
application scoring remain outside this small recorder's contract.

## Overlapping skills

Audit content and provenance before consolidating duplicate names. Identical
copies can have different host ownership; different copies can be intentional
variants. Prefer a documented canonical source and explicit host selection over
blind deletion, blanket replacement or assuming the first matching name wins.
