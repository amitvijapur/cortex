# Cortex Intake — review & add tools to Cortex from Telegram

A dedicated Telegram bot that turns "I found a cool skill/MCP/tool" into a
reviewed, approved entry in your `cortex.md` — without opening a session.

You drop a link. A headless `claude -p` reviews it against your registry and
replies with a verdict and **Add / Skip** buttons. Tap **Add** and it writes the
registry entry for you (backed up first). If the tool needs installing, the
commands go into a pending-installs queue you run later with one tap or by
saying "clear list" in a session. You can also just ask the bot questions about
your setup, and it answers read-only.

## How it works

| Component | Role | Shell access |
|-----------|------|-------------|
| `bot.py` | Telegram long-poller + orchestrator. Captures messages, spawns workers, handles button taps. | none |
| `worker.py review <id>` | Headless `claude -p` (scoped read tools). Fetches the link, judges it vs your registry, posts a verdict + buttons. | none |
| `worker.py build <id>` | Headless `claude -p` (Edit only, no Bash). Adds the registry entry to `cortex.md`, backed up first. Surfaces install commands, never runs them. | none |
| `worker.py ask <id>` | Headless `claude -p` (read-only). Answers a freeform question in Telegram. | none |
| `worker.py install <id>` | Runs the exact commands stored for a queue id, verbatim. The **only** shell-capable path. | **yes** |

### Safety model

- Review/build/ask workers run with `--permission-mode bypassPermissions` plus an
  explicit `--allowedTools` list — never `--dangerously-skip-permissions`, and
  never Bash. They cannot install anything.
- The installer is the only path that runs shell. Its callback carries **only a
  queue id**, never shell text. It re-reads the stored commands for that id and
  runs those verbatim, with no LLM in the loop, so nothing is generated at run
  time. It screens each command against a dangerous-pattern blocklist (`sudo`,
  `rm -rf /`, `curl | sh`, writes to shell rc files, …) and refuses matches.
- You see the exact commands in Telegram before you tap Confirm. The commands
  were authored by the build worker from the repo link you dropped, which is what
  makes running them safe.
- `cortex.md` is backed up before every autonomous edit.

## Setup

Requires the `cortex` CLI on your PATH (it manages the inbox and install queue)
and the [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) with a
logged-in session (the workers shell out to `claude -p`).

1. Put this folder at `$CLAUDE_DIR/cortex-intake` (default `~/.claude/cortex-intake`).
2. Create a **dedicated** Telegram bot via [@BotFather](https://t.me/BotFather).
3. `cp .env.example .env` and fill in `CORTEX_INBOX_BOT_TOKEN` and
   `CORTEX_INBOX_ALLOWED_IDS` (your Telegram user id — ask [@userinfobot](https://t.me/userinfobot)).
4. Run the bot:
   - **macOS:** edit `com.example.cortex-intake.plist` (username + `which python3`),
     copy to `~/Library/LaunchAgents/`, then `launchctl load` it.
   - **Any OS / quick test:** `python3 bot.py` (stays in the foreground).
5. Message your bot. Send `/help` to see what it can do, or drop a link.

## CLI

The queue and inbox are managed by the `cortex` CLI (see repo root):

```
cortex intake list|count|show|add|resolve      # the review inbox
cortex installs list|count|add|done|skip|clear # the pending-installs queue
```

Add these SessionStart hooks so pending items surface when you open Claude Code:
`cortex intake count --status unresolved` and `cortex installs count` (see the
main README for the hook snippets).
