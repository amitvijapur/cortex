# Evaluating the optional Jev adviser

The pilot does not establish better routing or lower cost. Its default evaluation
uses six public synthetic cases and fabricated adviser outputs to test replay,
accounting and reporting. The proposed labels are explicitly unreviewed. These
fixtures contain no tasks copied from a personal routing log.

The actual baseline remains normal session-model routing using Cortex's local
`hint` evidence. That command does not make a model request. The evaluation
imports the current `bin/cortex`, calls its actual hint renderer against an
in-memory history prefix, and imports its correction folding. It does not use
the stale “shipped Jaccard” description in `eval/hint_arms.py` as a baseline.
The current selector filters by class and returns the newest distinct
`(system, pattern, tier)` combinations. Different agents alone do not create
distinct combinations. Similarity is an annotation, not a ranking criterion.

## Offline checks

Run from the repository checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 eval/test_jev_eval.py
PYTHONDONTWRITEBYTECODE=1 python3 eval/jev_eval.py --out /tmp/jev-shadow-plumbing.json
PYTHONDONTWRITEBYTECODE=1 python3 eval/jev_eval.py --mode off --out /tmp/jev-off-plumbing.json
```

Output paths must be new files. Existing reports and known production state
filenames are rejected. Without `--out`, JSON goes to standard output. No
default evaluation writes to a production route log or launches a session model.

The shadow fixture produces three suggestions, two fallbacks and one explicit
choice. Its fabricated coverage is 50%, with one unknown request cost; total
cost must therefore remain `null`. Fabricated added latency has p50 of 5 ms and
p95 of 20 ms. These are expected fixture assertions, **not measured Jev
performance**. Off produces zero adviser requests and zero added adviser cost.
Session quality, total routing cost and end-to-end latency remain unavailable
until real session runs are imported.

## Dataset and historical replay

`eval/fixtures/jev-cases.json` is the format example. A dataset contains:

- `capabilities` and complete bounded `candidates`, including each candidate's
  identity, route combination, description and required capabilities.
- `history`, an ordered list of raw Cortex route and correction events. Preserve
  append order. Do not export a fully collapsed final history view.
- `cases`, each with a unique `id`, `task`, repeated-task `group`, `split` of
  `tune` or `heldout`, and `history_prefix`, the number of events available at the
  time of the query. An optional `target_event_index` must be outside that prefix.
- `query_class`, the session's independent classification at query time, if it
  existed. Never fill it from a target route or reviewed answer. Jev receives
  only the task text, not this class, the historical answer, or quality labels.
- `explicit_candidate`, when the user selected a workflow. This structured
  choice is passed to the runtime and bound into the session context hash.
- Optional `historical_candidate_id`, used only for historical agreement. A
  historical route and a shipped outcome are not correctness labels.
- `labels`, with `acceptable_candidates`, `acceptable_classes`, `reviewed`, and
  provenance. Reviewed labels additionally require `reviewer` and `reviewed_at`.

Both acceptable sets may contain the reserved outcome `abstain` for an ambiguous
task that should be deferred for clarification. Session runs record that explicit
outcome using `candidate_id: "abstain"` and `classification: "abstain"`. It is
not a callable candidate or an unavailable-route error. A missing/null candidate
is invalid rather than an implied abstention. Deferring an explicit workflow
choice is not counted as substituting a different workflow.

The raw prefix is sliced **before** folding corrections and outcomes. Later
reclassifications therefore cannot change the inputs to an earlier query.
The historical target itself must not be included. The author of a historical
dataset must establish the correct prefix and independent query class; the
harness cannot recover missing query-time context from a later route record.

Use separately reviewed representative and ambiguous tasks. Reviewer judgment
can admit several acceptable workflows. Review against the exact evaluated
candidate pool. Do not simply mark the included proposed fixture labels as
reviewed without that work. A group must belong to only one split, and identical
normalized task text must share a group. Related paraphrases also need the same
group; that semantic grouping remains the dataset author's responsibility.

Choose the threshold using tuning groups only. Freeze the threshold, model,
criteria, candidate pool, capability list, and protocol before evaluating held-out
groups. The harness does not optimize thresholds. For a tuning-only run, create
a separate dataset with only tuning cases; inspect held-out results only after
freezing the decision. It rejects rolling model aliases and records code, model,
dataset, candidate and capability fingerprints. Altered inputs invalidate reuse.

## Live Jev collection

Use a fresh current-session manifest as described in [Jev setup](jev-adviser.md). Its
session ID must match an independently supplied host ID. The evaluator applies
the same manifest validation as the runtime. A list of installed workflows alone
is not sufficient evidence of current callability.

With credentials available in the existing `TYPESAFE_API_KEY` environment
variable, the following explicitly authorizes at most six paid requests for a
six-case dataset. The runtime batches two independent questions in one request
and performs no automatic retries.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 eval/jev_eval.py \
  --dataset /tmp/jev-reviewed-cases.json \
  --manifest /tmp/jev-session-manifest.json \
  --session-id "$CORTEX_SESSION_ID" \
  --live --mode shadow --model jev-1.13.0 --threshold 0.8 \
  --max-calls 6 --out /tmp/jev-live-shadow.json
```

`--max-calls` is a hard request ceiling, not a dollar guarantee. Token-dependent
charges and incomplete usage from failed requests can make actual spend unknown.
Set the ceiling deliberately. Off runs cannot use `--live`. Missing credentials
return ordinary fallbacks with zero requests. Timeouts and failed calls retain
their attempted request count and unknown cost. There is no preflight model call.
The report records the returned model, criteria version, probabilities,
confidence, usage, latency and fallback reason from the runtime. A run with no
verified provider response cannot establish that Jev was tested successfully.

## Import comparable session decisions

The evaluator deliberately does not invent a session-model baseline or
automatically launch a paid agent. It exports the exact task, independent class,
structured explicit choice, current hint text, capabilities and candidates needed
to collect matched sessions. Use an isolated evaluation environment with
`CORTEX_HOME` redirected to a temporary directory. SessionStart hooks and routing
logs must not reach production state. Route only; do not execute the candidate
workflow during this routing experiment.

For every case, collect independent baseline, shadow and advisory sessions with
the same pinned session model, protocol, task, hint and candidate pool. Baseline
and shadow see no Jev suggestion. Advisory sees the public advisory view of the
saved Jev record and still chooses the final route itself. For a shadow record,
derive that view by copying the record, changing its `mode` to `advisory`, then
calling `cortex_jev.public_view`. Do not show the raw shadow record or its hidden
probabilities to baseline or shadow sessions. Saved advisory content is bound by
`advice_hash`, which covers the decision fields, model and criteria version.

Record the final decision, not just Jev's candidate. Record all session routing
attempts, retries and fallback reasoning exactly once; exclude Jev calls from
session attempt costs. Provide measured end-to-end wall time including hint,
advice wait and all session/fallback work. A parallel wall time is not the sum of
individual request times. Missing dollar costs must be `null`, never assumed zero.
Reuse the same saved Jev suggestion across the paired shadow/advisory scenarios.

The session import is a JSON object with a `runs` list. This is a schema example,
not a real result:

```json
{
  "runs": [{
    "case_id": "a-heldout-case",
    "arm": "advisory",
    "context_hash": "copy this case's context_hash from the report",
    "candidates_hash": "copy inputs.candidates_hash from the report",
    "advice_hash": "copy this case's advice_hash from the report",
    "synthetic": false,
    "model": "the actual pinned session model",
    "protocol_hash": "SHA-256 of the exact protocol supplied to the session",
    "candidate_id": "the final candidate chosen by the session",
    "classification": "build",
    "attempts": [
      {"cost_usd": null, "latency_ms": 350, "error": "timeout"},
      {"cost_usd": 0.01, "latency_ms": 1200}
    ],
    "end_to_end_ms": 1600,
    "reroutes": 0
  }]
}
```

Baseline and shadow runs must have `advice_visible: false` or omit that field.
Unknown, duplicate, mismatched-context or mismatched-model/protocol runs are
rejected. Advisory's advice hash must match the saved record. These provenance
checks detect accidental mixing; they are not proof against fabricated evidence.

Re-import without another paid call. Supply the same dataset, manifest candidate
pool, mode, model and threshold used for collection. An expired manifest can be
used for recorded analysis because no request or routing action is performed;
candidate and capability fingerprints must still match.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 eval/jev_eval.py \
  --dataset /tmp/jev-reviewed-cases.json \
  --manifest /tmp/jev-session-manifest.json \
  --mode shadow --model jev-1.13.0 --threshold 0.8 \
  --records /tmp/jev-live-shadow.json \
  --session-runs /tmp/jev-session-runs.json \
  --out /tmp/jev-compared.json
```

## Interpretation and rollout

Use `paired_heldout` for comparisons. It uses the same held-out cases with all
three session arms present for cost, request count, latency, reroutes and errors.
The broader `arms` blocks describe all collected session rows and can have unequal
denominators. `collection_totals` counts each actual saved Jev call once and all
session attempts once. Do not add the scenario totals across arms, since the same
saved Jev record is reused in shadow/advisory comparisons.

The report distinguishes adviser coverage/fallbacks and p50/p95 added Jev latency
from measured end-to-end session latency. Total routing cost includes session
retries and fallbacks plus adviser attempts. Known partial cost remains visible
when the true total is unknown. Unavailable candidates and explicit-choice
violations are reported. Missing reroute tracking stays unknown.

Quality is withheld unless all held-out cases have reviewed labels, matched real
session runs, and live Jev evidence. Conditional adviser accuracy uses only cases
where Jev suggested a route; final session accuracy includes fallbacks. Historical
agreement is a separate diagnostic and does not affect quality. No existing
reasoning or request is assumed to have been avoided. The report never
automatically recommends enabling advisory mode from point estimates alone.

Before enabling advisory, inspect paired decisions, explicit choices, errors,
coverage, latency and total known/unknown costs. Require a practically useful
held-out improvement with sufficient independent task groups. Additional API
latency or the absence of demonstrated benefit is a valid reason to leave it off.

The local pilot leaves these checks outstanding: authenticated provider schema
and pinned-model availability, actual confidence distributions, live failure and
latency behavior, billed usage reconciliation, independently reviewed labels,
matched normal-session/shadow/advisory decisions, and a held-out benefit analysis.
The recommendation with current evidence is to keep the default off and collect
explicit shadow evidence before considering advisory mode.
