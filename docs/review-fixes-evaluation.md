# Review fixes and evaluation gates

Follow-up: [Codex command attribution](codex-attribution.md) now provides opt-in
owner-verified commands and prospective host/thread logging. The full Codex
transcript and outcome-grading limitations described below still apply.

## Acceptance criteria, 29 September 2026

These are repair criteria, not evidence that routing quality improves.

- Agent sync refuses unsafe destination symlinks, including parent directories and metadata, before any write. External files and existing install bytes remain unchanged on refusal.
- Installed agent bytes correspond to the recorded source revision. Dirty source content cannot silently be attributed to HEAD. Existing description merges and conflict ancestry still work.
- Proposal rejection is persisted in YAML frontmatter and survives the next learning pass. Chat acknowledgements and checkboxes alone are not decision storage.
- A benchmark arm calls the production hint selector. Historical arms retain their identities. Comparisons use the same queries and legal chronological history, without later corrections leaking into earlier hints.
- Evidence reports expose host/period coverage and unknowns. Missing or ambiguous transcript joins are not successes or failures; reported dates derive from observed data.
- Existing offline regressions continue passing. Paid model runs and advisory activation require a separate decision.

## Evaluation sequence

1. Run deterministic repair regressions and the full offline suite.
2. Run production-aligned chronological hint replay. Treat agreement with recorded routes as historical agreement, not quality or optimality.
3. Review coverage by host and period before interpreting adherence. Preserve missing outcomes as unknown; never backfill success to pass a floor.
4. Reuse the prepared Jev pilot material only after checking provenance, frozen labels and protocol/hint compatibility. Existing baseline/shadow sessions do not establish Jev benefit.
5. Before a paid comparison, agree the case set, acceptable alternatives/abstention, held-out split, call/spend cap and quality/cost/latency criteria. Keep equivalent task context and candidate availability across arms. Review disagreements blind to arm identity.

Jev stays off until a measured benefit justifies the extra cost and dependency.
Graph and embedding proposals still need to beat the same cheap production baseline.

## Initial offline results, 29 September 2026

The chronological replay had 477 routes and 474 eligible queries. Production
distinct-class retrieval recovered the recorded route in its top five on 103
queries (21.7%); historical non-distinct recency recovered 98 (20.7%), and the
query-legal graph arm recovered 92 (19.4%). Only 144 queries had their recorded
route anywhere in the prior pool. These are historical agreement scores on a
growing log, not held-out route-quality labels or a new preregistered experiment.
No graph rollout is supported. Local embeddings were not rerun in this repair.

The existing private Jev pilot gives no advantage on its six easy cases: baseline,
shadow and advisory each match all six accepted labels. Costs for session models
are unknown, and the baseline used unfiltered hints. See
[the pilot limitations](jev-pilot-results.md). No paid calls were made for this
repair, and its historical freeze was preserved.

Evidence coverage remains a separate bottleneck. The log contains no explicit
host field for these historical routes, so recorded hosts correctly remain
unknown. Only Claude transcripts have a supported reader. A safe Codex adapter
needs fork/subagent ownership validation before importing inherited histories.
Adding that adapter and explicit host capture is follow-up work, not a capability
delivered by this repair. Missing outcomes must not be filled with guessed success.

The last dry-run snapshot recorded outcomes for 383/477 routes (80.3%), below the
85% floor. September has 18/284 anchor-attributed routes (6.3%); across the whole
log only 75/477 are attributable. Hint-before-route is 38/75 (50.7%), not a rate
over all hosts. The live log can change concurrently, so these denominators belong
to this snapshot, not a frozen quality benchmark. The gate correctly exits nonzero.

## Verification

155 counted repository tests passed, including two separately rerun default
skips. The eight-section CLI suite, delegation skill contract and twelve private
pilot regressions also passed. Independent re-review found no remaining blockers
in these fixes. `git diff --check` passed.

Offline suites cover CLI behavior, runtime integrity, evaluation integrity,
installation/sync, Jev adapter/evaluation, frontend library/installation, hint
selection, proposal decisions and the delegation skill contract. The two default
runtime skips were separately run against a copied personal intake module in
disposable state and passed. The old untracked intake-confinement suite was left
untouched and was not claimed as passing.

Independent review reproduced and prompted additional regressions for singleton
anchor timestamp drift, append-only outcome/reroute folding and case-insensitive
sync metadata collisions. Sync preflight is not a transaction or protection
against concurrent hostile path replacement. Do not run concurrent install
mutations against the same destination.

The eval-harness workflow kept deterministic repair checks separate from routing
quality claims. The next useful experiment is a labelled representative task set,
not another easy six-case pilot or a guessed outcome backfill.
