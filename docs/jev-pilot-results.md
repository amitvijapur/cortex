# Jev pilot evidence, 20 September 2026

## Decision

Keep routine routing off. The local pilot is implemented and tested, but advisory
mode is not justified by measured routing benefit yet. The next experiment is a
bounded live shadow run with reviewed cases and comparable session-model decisions.

This is a working integration and evaluation harness, not a report of Jev beating
Cortex. `TYPESAFE_API_KEY` was absent from the build environment, and no live Jev
requests or paid session-model benchmarks were made.

## Established locally

- The installed Cortex CLI matched the checkout before the change. The baseline
  hint is a local, class-filtered recency lookup with distinct
  `(system, pattern, tier)` combinations. It has no model inference cost.
- Off mode makes no network calls, reads no manifest and writes no experiment
  records. Existing hint behavior is unchanged.
- Shadow mode persists the full experimental record while suppressing the
  suggestion from public output. Advisory mode exposes validated advice only.
- Explicit choices bypass Jev. Missing credentials, stale manifests, unavailable
  candidates, uncertain answers, malformed API data and timeouts fall back.
- Transport has a total deadline and no automatic retries. Failed requests with
  unknown incurred cost remain unknown in evaluation, rather than counting as free.
- Experiment records stay separate from production route/outcome records. Replay
  reconstructs each raw event prefix before invoking the production hint renderer.
- Installation in disposable homes includes the sidecar and preserves existing
  registry/log contents. Symlink conflicts are rejected before copying files.

The checks include 22 adviser tests, 24 new evaluation tests, all eight sections
of the existing CLI behavioral suite, 18 existing evaluation integrity tests and
11 installer regressions. Runtime integrity ran 22 cases, with 20 passing and two
skipped as described below.
Two existing runtime-integrity cases require a separately staged personal intake
module and are skipped in the ordinary repository-only run. They are unrelated to
Jev and were not claimed as passing here.

Independent review identified and prompted fixes for malformed numeric responses,
host-session matching, explicit override propagation, and matching cost-comparison
denominators. Runtime and evaluation re-reviews found no remaining release-blocking
issues. The final abstention-outcome change passed its regression run.

## Offline evaluation

Run the public synthetic fixture with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 eval/jev_eval.py --mode shadow
```

Its six authored, unreviewed cases exercise three suggested routes, uncertainty,
a timeout with unknown cost, and an explicit user choice. Those predictions,
latencies and costs are deliberately fabricated fixtures. The report labels them
`synthetic_plumbing_only`, withholds quality metrics and does not infer savings.
They demonstrate that the reporting path works, not how often Jev is right.

The historical 42-task personal replay set has no independently reviewed labels.
It was inspected during scoping, not uploaded, published or treated as a gold set.
The new harness executes the actual hint code on supplied history; it does not
reuse the stale headline ranker arms as a production baseline.

## Exact live checks remaining

1. Configure a TypeSafe credential and validate one real request against the pinned
   model, including the returned model ID, probability map and usage fields.
2. Capture the host's actual callable capabilities, test a fresh session manifest,
   and verify that a shadow suggestion stays invisible until the baseline route
   has been recorded.
3. Independently review representative and ambiguous tasks, allowing multiple
   acceptable workflows and abstention. Group related tasks and freeze a held-out
   split before tuning thresholds.
4. Collect matched current session-model runs with the same task context, hints,
   capability pool and protocol: baseline, shadow and advisory. The supplied
   session-record importer is host-neutral; it does not invoke a hidden substitute
   Claude runner and call that a Codex baseline.
5. Measure final-route quality, unavailable candidates, explicit-choice violations,
   abstention/coverage, reroutes, p50/p95 latency and total routing cost. Include
   failed attempts, retries, fallback reasoning and final session reasoning.
6. Check confidence calibration and ambiguous cases on held-out data. Review
   disagreements blind to which arm produced them, and decide whether the benefit
   exceeds the added latency, cost and operational dependency.

No production-mode change follows automatically from these checks. A null result
is a valid reason to retain off mode. The pilot does not demonstrate reduced agent
execution cost or improved completed-build outcomes; those need downstream evidence.

See [setup and rollback](jev-adviser.md) and [evaluation procedure](jev-evaluation.md).
