# Astra and ChatGPT Work delegation

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
