# CLI reference

The CLI records and inspects routing decisions. It does not dispatch the workflow named in a route. The agent following the protocol performs that work.

From a checkout, run `python3 bin/cortex --help`. For an installed copy, use `python3 ~/.claude/bin/cortex --help`, adjusting the path for a custom state root. The recipes below use this shell function so commands work without adding the executable to `PATH`:

```bash
cortex() {
  python3 "${CORTEX_HOME:-${CLAUDE_DIR:-$HOME/.claude}}/bin/cortex" "$@"
}
```

Use `cortex <command> --help` for the complete current flags. See [setup](setup.md#custom-state-directory) for state resolution.

## Declare and record a route

These commands write to the routing log. Declare the routing line before executing the task, then record it. The example is illustrative and does not invoke a workflow:

```bash
cortex log-line "Direct > plan-and-verify @ L3" "refactor auth middleware" \
  --class build \
  --tier-reason "Session compatibility needs an independent verification pass" \
  --route-confidence high --tier-confidence med --spec-confidence high
```

The named-flag form records the same fields:

```bash
cortex log --task "refactor auth middleware" --class build \
  --system Direct --pattern plan-and-verify --tier L3 \
  --tier-reason "Session compatibility needs an independent verification pass" \
  --route-confidence high --tier-confidence med --spec-confidence high
```

Classes are `build`, `review`, `plan`, `research`, `debug`, `design` and `quickfix`. Tiers are `L1` through `L4`. Confidence values are `high`, `med` and `low`.

Both forms accept `--system-reason`, `--project`, `--redirect-from`, repeatable `--legs` and `--model`. `log` also accepts `--agent`. Use real callable specialists in the agent field and separate work items with `--legs`. The model flag records provenance; it does not switch the executing model. Its default comes from `CORTEX_MODEL` or `CLAUDE_MODEL` when set.

## Retrieve evidence and inspect history

```bash
cortex hint "refactor the session store" --class build
cortex hint "refactor the session store" --class build --top 10
cortex show --last 20
cortex show --project cortex
cortex history <event_id>
```

`hint` returns recent distinct routes, filtered by class or tier if requested. It displays lexical similarity and outcomes as context, not ranking weights. `--min-similarity` is an optional filter, not the default ranking. Start with class alone when the log is small. An empty log reports that no evidence is available.

`show` defaults to 20 routes. Its project filter uses the display label; automatic outcome selection uses canonical directory and session identity instead. `history` accepts a route ID or legacy task hash and prints the event chain. See [history and learning](history.md) for event semantics.

## Record outcomes and corrections

```bash
cortex outcome shipped
cortex outcome partial --note "stopped at the migration step"
cortex reroute --to "Direct > batched-edits @ L2"
```

Outcomes are `shipped`, `abandoned`, `partial` and `corrected`. Outcome and reroute updates default to the latest route in the current canonical working directory and agent session, including routes already marked partial. They do not fall back to another project or session.

For older routes or shells without a session identity, inspect `cortex history <task_hash>` and pass the exact route ID with `--ref`:

```bash
cortex outcome shipped --ref <event_id>
cortex reroute --to "Direct > batched-edits @ L2" --ref <event_id>
```

Ambiguous legacy references are reported and left unapplied. Corrections append events; they do not replace the original route.

## Learn and audit

```bash
cortex learn --no-proposals
cortex learn
cortex learn --check
cortex audit-tiers --tier L3
cortex doctor --no-probe
```

`learn` detects repeated `(class, system, pattern)` tuples and normally writes proposal files. The default repetition threshold is three; change it with `--threshold`. `--no-proposals` reports without writing proposals. `--check` gives terse output and is silent when nothing is pending. `--include-actioned` includes patterns already approved, rejected or superseded.

`audit-tiers` defaults to L3 and L4. Repeat `--tier` to select multiple tiers. To append a reviewed tier correction:

```bash
cortex audit-tiers --reclassify <task_hash> --to L2 --note "why L2 was sufficient"
```

`doctor` checks drift among the framework, installed skills and log. `--verbose` includes passing checks. `--weekly` writes a gate timestamp and suppresses repeat runs inside seven days. Ordinary checks may invoke advisor CLI version commands; `--no-probe` avoids those invocations. `--deep-probe` makes real prompt calls and requires authorization for model spend.

## Discovery and optional features

| Command | Purpose | State or external activity |
|---|---|---|
| `cortex init --dry-run` | Print a discovery summary | Reads local configuration without writing inventory |
| `cortex init` | Scan tools for registry preparation | Writes `cortex-inventory.json`; does not synthesize a registry |
| `cortex advise "task" --mode off --json` | Inspect the disabled Jev adviser path | Off mode makes no network request or experiment write |
| `cortex skill-use --help` | Inspect opt-in skill evidence flags | Recording requires an exact route ID and actual skill file |
| `cortex intake list` | Inspect the capture inbox | Local inbox read |
| `cortex installs list` | Inspect pending setup commands | Lists commands; does not execute them |

Jev shadow and advisory modes require a fresh manifest of capabilities available in the current session. They have separate experiment and network behavior. Read [Jev setup](jev-adviser.md) before enabling them.

[Skill-use evidence](skill-evidence.md) records self-reported reads, invocations and applications using canonical paths and content hashes. It does not automatically measure usage or establish successful application.

The personal Telegram intake service is a separate installation. See [intake operations](intake-operations.md) before operating its worker. Queue mutation commands are listed by `intake --help` and `installs --help`; reviewing a queued command does not authorize running it.

## Agent skills

In the default Claude Code setup, `/cortex-log` reviews routes, `/cortex-learn` detects patterns and writes proposals, `/cortex-learn --check` gives a terse pending check, and `/cortex-reroute "new route"` records a correction. `/cortex-init` combines CLI discovery with agent-led registry generation. Skill availability varies by host and destination; see [the installation table](setup.md#what-the-installer-changes).

## Evaluation commands

Checks live in `eval/`, not in the CLI:

```bash
python3 eval/score_adherence.py --check
python3 eval/route_eval.py --dry-run
PYTHONDONTWRITEBYTECODE=1 python3 eval/test_cortex_cli.py
```

The first scores the selected log, the second lists consistency cases without model calls, and the third runs behavioral CLI tests with temporary fixtures. A real `route_eval.py` run invokes models and can spend money. See [evaluation](evaluation.md) for evidence and limitations.
