# Astra and ChatGPT Work delegation

## Publish reviewed repairs, 14 September 2026

- [x] Verify the repository changes and regressions before publication.
- [ ] Commit and push the reviewed frontend library and Cortex repairs.
- [ ] Confirm the remote commit and record the result. Do not merge.

Almanac stays running by explicit user request. Intake and its scout stay paused.
Personal intake state and the private repair bundle remain outside Git. Preserve
the pre-existing untracked AGENTS.md and original intake test fixture.

## Astra review repairs, 13 September 2026

- [x] Stop Cortex Telegram intake and disable its weekly scout reversibly.
- [x] Repair queue concurrency and route/correction identity.
- [x] Repair evaluation collapse, caching, nullable text and comparator consistency.
- [x] Repair installer ownership, sync conflicts and frontend edge cases.
- [x] Restore and verify intake confinement with a persistent pause gate.
- [x] Install verified live repairs with backups, keeping Telegram stopped.
- [x] Run affected suites and record remaining evidence gaps.

### Repair verification

- Existing CLI suite: all eight sections pass.
- Runtime integrity: 22 pass, including mixed CLI/intake writers and same-name projects.
- Evaluation integrity: 18 pass, including interrupted attempts and transcript attribution.
- Installer/sync: 11 pass. Frontend: 17 pass; frontend installer: 4 pass.
- Delegation contract, generated-library drift (53 entries), shell syntax and diff checks pass.
- Final intake suite: 51 pass, 2 obsolete blocklist tests skipped, 1 observed outbound-network expected failure.
- Independent Astra re-review cleared targeted intake fixes. All builds are now
  stage-only, with restricted reads and no automatic registry application.
- Five personal intake files installed and compared to the tested bundle. Live
  worker and bot both refuse startup under `.paused`; reminder is silent.
- Backups: `/Users/amit/.claude/cortex-repair-backup-20260913-NYrscX/`.
- Cortex doctor: 24 pass, 5 warnings, 0 failures. Warnings concern personalized
  skills and never-used registrations, not evidence to retire those tools.
- No-model routing and replay dry runs cover 14 cases and 42 items. No new ranker
  was promoted. Historical outcome coverage remains around 81%, below the 85% floor.
- Real model CLI compatibility and outbound-network isolation remain unverified
  or incomplete. Intake and scout must stay paused. The separate Almanac bot was
  left running, confirmed by Amit on 14 September. Seven queued intake items are preserved.
- No push or merge. Original untracked AGENTS.md and intake test fixture preserved.

Operational details: [intake maintenance](../docs/intake-operations.md). Private
security evidence and tests remain in `.omc/intake-repair/REPORT.md` and its bundle.

## Frontend design library, approved 13 September 2026

- [x] One Astra review of the initial plan; present revised scope.
- [x] Import guidance and 46 resource links plus seven books, retaining provenance.
- [x] Build a validated catalogue and searchable static directory.
- [x] Add a focused skill and dedicated pointer installer.
- [x] Verify migration, generated output, interaction logic, and installation.
- [x] Record results and usage in the project build log.
- [ ] Visual browser verification: blocked by browser URL policy for the local file.

The library is on demand. Existing routing algorithms, default routes, and the live
CLI remain unchanged. Markdown guidance and resources.json are editable sources;
the legacy HTML is a dated snapshot. Private assets stay outside version control.
Public catalogue updates are editorial, with evidence recorded rather than
automatically promoted into routing rules. No new Cortex subcommands in this build.

- [x] Trace the existing Fable and Opus delegation mechanism.
- [x] Identify the live Codex and ChatGPT Work task primitives and their boundaries.
- [x] Add a reusable `cortex-delegate` skill with separate Codex and Work lanes.
- [x] Add installation support for Codex without changing the Claude-only skills.
- [x] Add deterministic contract tests and run the skill validator.
- [x] Document the design, limitations, and live smoke-test plan.
- [x] Review the diff independently, fix findings, and report what remains untested.

## Review

- Contract test passes.
- Skill Creator validator passes under the existing Anaconda Python. The active Homebrew Python lacks PyYAML, which is a validator dependency rather than a skill defect.
- Installer passes with a Codex home and on a Claude-only machine. The latter does not create a Codex directory as a side effect.
- Full Cortex CLI suite passes.
- Independent Terra review found one high-severity boundary leak: the first draft conditionally allowed `wait_threads` for Work if a later runtime claimed support. The restriction is now absolute, and the test pins `wait_threads` to the Codex section.
- No live task was created. The smoke test remains opt-in because both lanes create visible user-owned tasks.
