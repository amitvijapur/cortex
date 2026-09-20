# Personal Telegram intake maintenance

The personal intake bot is a separate installation under
`~/.claude/cortex-intake`, not part of the repository installer. Its inbox and
install queue are shared with the Cortex CLI. Both writers must hold an exclusive
lock on `<queue-path>.lock` across the entire read, mutation and atomic replacement.

## Paused operation

The 13 September 2026 repair session disabled and unloaded the intake launchagent
and its weekly scout. It also placed `.paused` in the intake directory. Repaired
workers and the bot check this marker before launching work or sending messages.
The personal session-start intake reminder respects the same marker. Existing
queue items, approvals and configuration are retained, not processed or deleted.

Pausing is reversible. Do not remove the marker or re-enable launchagents as part
of a routine code update. Resuming needs an explicit user request and a separate
compatibility check with the installed model CLI. A test double completing a job
does not establish that real authentication, caches and hooks work under the
restored sandbox.

The separately installed Almanac Telegram bot is not the intake worker or scout.
Check its service state separately and do not describe it as paused unless it has
actually been stopped.
Amit explicitly asked to leave Almanac running on 14 September 2026.

## Repair evidence and limits

The private staged repair lives in `.omc/intake-repair/`. It includes the worker,
policy, common helpers, bot, and isolated acceptance tests. It is intentionally
outside the public source tree because the original personal integration contains
local paths and identifiers. The user's pre-existing untracked
`eval/test_intake_confinement.py` is preserved. Its corrected copy is in staging.

Model jobs must invoke the OS sandbox, use restricted readable paths and write
only staging artifacts. Authenticated approval permits preparation of a proposed
diff, not automatic registry application. Every build is retained for local
exact-diff review. Unavailable confinement must refuse the job.
Telegram shell installation is disabled; queued commands require local review.

No model-based routing evaluation or real Telegram intake job is needed to run
the regression checks. Development-set retrieval numbers remain diagnostic,
not evidence to promote a new ranker. Missing historical outcomes remain a data
quality issue and must not be invented to make the adherence gate green.
