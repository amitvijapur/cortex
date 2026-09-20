# Optional Jev routing adviser

Jev advises the session model about task classification and a workflow to use.
The existing session model still chooses effort, plans and performs the work,
checks permissions, and verifies the result. This pilot does not dispatch agents
or replace Cortex's routing protocol. It starts **off**.

## Modes and failure behavior

| Mode | Network | What the routing model sees |
|---|---|---|
| `off` | None | Disabled status; no manifest reads or experiment writes |
| `shadow` | At most one request | Status only; the suggestion is recorded separately |
| `advisory` | At most one request | A validated classification and workflow suggestion, or fallback |

Missing credentials, unavailable or stale candidates, uncertain answers, malformed
responses, timeouts and API failures return fallback status. Continue the usual
classification, `hint`, effort selection and routing. An explicit workflow choice
short-circuits the model call. An unavailable explicit choice requires the normal
session handling; the adviser must not substitute another workflow.

Shadow records must be withheld from the model making the baseline decision.
Reading them before choosing a route would turn shadow into advisory and invalidate
the comparison. Do not record experimental suggestions as production routes or
attach production outcomes to them.

## Installation and credentials

The pilot uses Python's standard library and the documented TypeSafe HTTP API.
No new Python package is required. Run from the checkout first:

```bash
python3 bin/cortex advise "build a small API endpoint" --mode off --json
```

The normal `bash install.sh` installer copies both `bin/cortex` and
`bin/cortex_jev.py` to the configured Cortex home. Its destination checks still
apply. Back up the existing CLI and sidecar, if present, before upgrading. The installer
preserves a personalized registry and writes the new template beside it for manual
review. Do not replace your registry wholesale just to enable this feature.

Configure `TYPESAFE_API_KEY` through your existing secret manager or shell session.
Do not put the key in a manifest, source file, task text, command-line argument or
committed `.env` file. The adviser does not search private credential files.
Only the task summary and candidate descriptions are sent to TypeSafe; entire
transcripts, repository files and production routing history are not uploaded.

The model is pinned to `jev-1.13.0`. Its published input price at implementation
time is $0.042 per million tokens, with no output charge. Recorded cost is an
estimate from returned usage and the version-specific rate, not an invoice.
Failures after an attempted request can have unknown cost; unknown is not zero.
Recheck pricing and validate thresholds before changing versions.

## Current-session capability contract

The calling host supplies a JSON manifest containing its session identity, a
generation timestamp, capability identifiers and complete workflow candidates.
Each candidate declares the capabilities it requires. A candidate can combine a
workflow and specialist, but does not select an effort tier.

This is an attestation boundary. Cortex can validate identity, freshness, required
capability membership and response shape. A standalone CLI cannot independently
inspect the agent host's live tool catalogue. The host must produce the manifest
from its current exposed tools, agents and skills and refresh it when they change.
Never derive it solely from `cortex init`, a filesystem scan or the registry.
Missing reliable capability information means fallback.

The manifest schema is version 1. `session_id` must match the supplied host session;
`generated_at` is an ISO timestamp with timezone. The pilot allows a maximum age of
300 seconds (and 30 seconds of clock skew into the future), 256 capability IDs,
32 candidates, and a 64 KiB manifest. Task summaries are limited to 8,000 characters.
Candidate IDs are unique, and `abstain` is reserved. Every candidate needs `system`,
`pattern`, `description`, and a nonempty `requires` list drawn from `capabilities`.
`agent` is optional. The manifest is checked again after the API response.

[The example manifest](../examples/jev-session.json) illustrates two workflows for
a host exposing local commands and worker agents. Its identity and timestamp are
deliberately invalid placeholders. Review and replace its capabilities and candidates
against the actual current session before using it. Do not advertise an unavailable
worker or treat the example as runtime discovery.

For a Codex host that has verified those exact example capabilities, this creates
a fresh temporary copy using `jq` and invokes one shadow decision:

```bash
test -n "$CODEX_THREAD_ID" || exit 1
jev_manifest=$(mktemp)
jq --arg session "$CODEX_THREAD_ID" \
   --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
   '.session_id = $session | .generated_at = $now' \
   examples/jev-session.json > "$jev_manifest"
python3 bin/cortex advise "Implement a small CLI feature with tests" \
  --mode shadow --manifest "$jev_manifest" \
  --session-id "$CODEX_THREAD_ID" --json
```

This needs the API key already configured. Without it, the result is a safe fallback,
not a live Jev test. `jq` is only an example preparation tool, not a Cortex dependency.
Other hosts can write the same JSON using their existing session integration.
Recognized session identity variables are `CORTEX_SESSION_ID`,
`CLAUDE_CODE_SESSION_ID`, `CLAUDE_SESSION_ID`, and `CODEX_THREAD_ID`, in that order.
An explicit `--session-id` conflicting with the detected identity is rejected.

For an advisory experiment, change `--mode shadow` to `--mode advisory`. The
`CORTEX_JEV_MODE` environment variable can set the default for `advise`, but it does
not cause `hint` or hooks to invoke Jev. Explicit `--mode` takes precedence.
`--explicit-candidate delegated-build` preserves that user-selected candidate and
makes no request. The host must pass explicit user choices through this flag rather
than relying on their detection from free text.

The default threshold is `0.8` for both returned confidence and selected-option
probability on each question. The total network deadline defaults to two seconds
(`--timeout`, range 0.05 to 10). There are no automatic retries. The transport uses
the fixed HTTPS API endpoint, rejects redirects and does not inherit proxy settings.
An environment that requires a proxy will fall back rather than silently reroute
credentials.

Experiment JSONL records are stored under
`$CORTEX_HOME/experiments/jev/<session-hash>.jsonl` (default Cortex home `~/.claude`).
They include model and criteria versions, manifest fingerprint, distributions,
confidence, usage, cost estimate, latency, and fallback reason. The task and session
identity are hashed; task plaintext and API credentials are not stored. Candidate
descriptions are retained, so keep them free of private task details. Never commit
these local records. If the experiment log cannot be written, advice is withheld.

## How this fits builds

At a build's routing step, a host with Jev explicitly enabled supplies a short task
summary and current candidate menu. In advisory mode the session model considers
the recommendation, chooses effort, consults normal history, and executes its
chosen workflow. In shadow mode it chooses without seeing the recommendation.

Use the existing permission and policy checks at execution time even when the
suggestion is confident. Jev's confidence summarizes the concentration of its
answer distribution; it is not a percentage guarantee of correctness. A confidence
threshold is a pilot setting that needs calibration on separate tuning cases.
Future advice about build progress or verification needs its own scoped evaluation;
it is not enabled by this routing pilot.

## Evaluation and rollout

See [the evaluation guide](jev-evaluation.md). Local fixture tests establish input
validation, fallback behavior and accounting. They do not establish Jev accuracy,
confidence calibration, real latency or benefit to final session decisions.

The actual current hint baseline is class-filtered recency over distinct
`(system, pattern, tier)` routes. Historical outcomes are reconstructed from the
events available at each query. The old similarity-ranker descriptions and main
arms in `eval/hint_arms.py` are not the production baseline for this pilot.

Keep Jev off unless explicitly running an experiment. Before routine advisory use,
obtain reviewed cases, tune thresholds on a separate split, compare identical
candidate pools with and without advice, and include final session reasoning and
fallbacks in latency and cost. Review disagreements blind to the generating arm.
The important outcome is final-route quality, not conformity to historical routes.

## Rollback

1. Set `CORTEX_JEV_MODE=off`, or remove it, and stop invoking `advise` in the host's
   routing instructions. An explicit `--mode off` overrides the environment.
2. Continue the existing `hint`, `log-line` and outcome protocol. No production
   log migration or repair is needed.
3. If reverting the binaries, restore the backed-up CLI and sidecar as a matched
   pair. A pre-pilot CLI has no sidecar dependency; restore that CLI and leave the
   unused adviser file in place or archive it. Preserve experiment records for
   analysis; do not merge them into production.

No session-start hook, global permission setting, installed agent or personalized
registry is modified by the adviser command.

## Sources

- [TypeSafe HTTP request and response contract](https://docs.typesafe.ai/api)
- [Model versions and pricing](https://docs.typesafe.ai/models)
- [Confidence semantics](https://docs.typesafe.ai/confidence)
- [Workflow design guidance](https://docs.typesafe.ai/concepts/how-to-build-with-system-one)
- [User-supplied Jev workflow context](https://x.com/0xCodila/status/2100984487802708306)

The social post informs the fresh-candidate-menu design and independent completion
checks. Its demonstrations are not evidence of Cortex performance.
