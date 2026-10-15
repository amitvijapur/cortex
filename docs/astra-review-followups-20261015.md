# Astra review follow-up repairs, 15 October 2026

## Scope and acceptance

An independent Astra review of the merged audit repairs reproduced six remaining
defects. This follow-up is restricted to those defects, with synthetic fixtures
and no historical evidence rewrites or live model evaluations.

| Area | Required behaviour |
| --- | --- |
| Parallel hints | A hint finishing after route declaration cannot inform the route, even when separate calls share a start timestamp. A combined hint/log shell command can count as run, never as informing its already-composed declaration. |
| Outcome parsing | Quoted task text containing an outcome command must not become ceremony evidence or an outcome-command lag. Actual successful outcome invocations remain detectable. |
| Codex evidence scope | Commands-only sessions must not enter orphan failure/outcome inference. Quoted references to git revert are not evidence of reverted work. |
| Evidence isolation | A route-log symlink resolving to the regular evidence file must be rejected before appending. Existing symlink/hardlink rejection and normal separate-file writes remain intact. |
| Custom installations | Installed skill commands must locate the configured CLI with default and custom roots, including spaces, while preserving installer provenance and customization checks. |
| Doctor references | Source URLs must not be validated as local executable paths. Genuine broken local references must still be reported. |

## Verification

All six fixes are implemented. New regressions failed before their corresponding
fixes. The combined offline verification covers 15 test files: 221 individual
tests pass, including the final 31-test installer run. The two optional
staged-intake integration cases are intentionally skipped.
The eight-section CLI suite and delegation contract checks pass. Shell syntax and
diff whitespace checks pass. No intake confinement or paid model evaluation ran.

Actual copied skill commands are exercised under default, empty, CLAUDE_DIR,
CORTEX_HOME and combined overrides, using paths with spaces and repeat installs.
Custom overrides must remain exported in the invoking agent's environment. The
installer prints quoted, root-specific verification commands and the export.

A fresh Astra intent review cleared the evaluation and isolation changes, with
five additional synthetic test groups. The independent standards review found
that URL exclusion could consume an adjacent broken local path. The follow-up
patch passes 88 adjacency cases and preserves common URL syntax, including IPv6,
balanced parentheses, parameters and query strings. Review also caught quoted
punctuation paths; extracting literal quoted paths first closes that regression.
Quoted-path fixtures cover 96 cases, with another 16 for preceding prose
apostrophes. Astra's standards re-review clears the final bounded contract after
51 independent boundary checks. This is not a general shell-parser guarantee.

Six installed routing skills received only the root-resolution edits. Three
source-identical copies have verified installation hashes; the three customized
copies retain their personal wording and remain unstamped. Doctor with the
correct configured Obsidian root reports 27 passes, eight known warnings and no
failures. Personal backups and detailed recovery paths stay outside the repo.

## Limits

The shell parser remains deliberately conservative. Unsupported commands are
unknown, not evidence of non-use. The file-identity guard rejects the reproduced
alias; it is not a general defense against arbitrary concurrent filesystem
replacement. Personal customization differences remain visible rather than being
overwritten to silence Doctor. Implementation was completed before publication;
the user subsequently authorized a scoped push and merge of these verified fixes.
Unrelated working-tree changes and paused services remain untouched.
