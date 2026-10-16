# Setup and host integration

The [README quick start](../README.md#quick-start) covers the default Claude Code installation. This guide explains the files it installs, manual integration with other agents, and optional state and audit configuration.

## What the installer changes

Run `./install.sh` from the repository with Bash and Python 3 available. The default state directory is `~/.claude`. The installer creates missing installation directories and an empty routing log, preserves an existing `cortex.md`, and leaves `settings.json` alone.

| Source | Destination |
|---|---|
| `bin/cortex` | `<state-dir>/bin/cortex` |
| `bin/cortex_jev.py` | `<state-dir>/bin/cortex_jev.py` |
| `bin/cortex_skill_evidence.py` | `<state-dir>/bin/cortex_skill_evidence.py` |
| `cortex-log`, `cortex-learn`, `cortex-reroute`, `cortex-init` skills | `<state-dir>/skills/` |
| `cortex-log`, `cortex-learn`, `cortex-reroute`, `cortex-delegate` skills | `${CODEX_DIR:-${CODEX_HOME:-~/.codex}}/skills/`, if that Codex home already exists |
| `cortex-log`, `cortex-learn`, `cortex-reroute` skills | `~/.agents/skills/`, if `~/.agents` already exists |
| `templates/cortex.md` | `<state-dir>/cortex.md`, or `cortex.md.new` if a registry already exists |

The installer preflights every destination before copying. It refuses symlinks, including linked ancestors, and stops on personalized skill files. Unchanged prior releases are recognized through installation hashes or exact versions in this checkout's Git history. Preserve and merge a reported customization manually.

Re-running the installer updates the CLI and recognized skills. It does not merge a new framework into your existing `cortex.md`. Review `cortex.md.new` and merge the changes you want.

## Discovery versus registry generation

`python3 bin/cortex init` scans agents, skills, commands, MCP server names, hooks, plugins, other-agent configuration files and relevant CLIs. It writes `<state-dir>/cortex-inventory.json`. Use `init --dry-run` to print the summary without writing that inventory. Discovery does not install tools or synthesize a registry.

The **`/cortex-init` agent skill** runs discovery, resolves ambiguities, drafts a registry and proposes a merge. It requires a backup and confirmation before writing the personalized registry. The installer currently puts this skill only in the primary state directory's `skills/`, normally the Claude Code home. It does not install it into the Codex or shared skill destinations.

On another host, use the discovery inventory to build the registry manually or ask that host to draft a merge using the [registry guide](registry.md). Treat detected configuration as evidence to inspect, not proof that a tool is callable in the current session.

## Other agents

Cortex's protocol is Markdown and its CLI is Python. A host must load the protocol, expose the relevant tools and allow the agent to run the CLI. Installation alone does not provide those host integrations.

The following are manual integration examples. Check the host's current instruction-loading rules and verify that a fresh session actually sees the protocol.

| Host | Integration approach | Setup distinction |
|---|---|---|
| Claude Code | Reference `cortex.md` from `CLAUDE.md` with `@cortex.md` | Guided `/cortex-init` skill in the primary home |
| Codex or another `AGENTS.md` host | Put the protocol in the applicable `AGENTS.md`, or instruct the agent to read its canonical file | Do not assume Claude's `@file` inclusion works; installer adds maintenance and delegation skills to an existing Codex home |
| Cursor | Add the protocol through project rules or user rules | Manual registry and CLI setup |
| Gemini CLI | Include the protocol in `GEMINI.md` | Manual registry and CLI setup |
| Windsurf | Add the protocol through its workspace rules | Manual registry and CLI setup |
| Aider | Load the protocol as a read file in its configuration | Manual registry and CLI setup |

Keep one canonical registry where possible. After integration, ask the agent to describe the loaded routing protocol, run a bounded task, and inspect the resulting route and outcome. A tool named in an example registry is not necessarily installed or available.

New route events carry host and session provenance where available, including `CODEX_THREAD_ID` for Codex. Optional [Codex command attribution](codex-attribution.md) checks command ownership. It does not establish full transcript adherence or successful work, and old process-based references remain unknown.

## Custom state directory

State resolution is `CORTEX_HOME`, then `CLAUDE_DIR`, then `$HOME/.claude`. Export the same root when installing and in the environment where the agent invokes skills:

```bash
export CORTEX_HOME="$HOME/.cortex"
./install.sh
python3 "$CORTEX_HOME/bin/cortex" doctor --no-probe
```

A one-shot installer environment override does not persist in future sessions. Keep the export in the appropriate shell or host environment. Paths containing spaces are supported when quoted. The installer prints commands for the selected root.

For a custom root, configure the host to load that root's `cortex.md` explicitly. The CLI's state override does not change which instruction files the host loads. `CODEX_DIR` and `CODEX_HOME` control the optional Codex skill destination separately from routing state.

## Session start audit

The installer does not add hooks. In Claude Code, the following optional `SessionStart` hook runs a weekly setup audit and supplies its output as session context. It requires `jq` and uses the default installation path:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "out=$(python3 ~/.claude/bin/cortex doctor --weekly --no-probe 2>/dev/null); if [ -n \"$out\" ]; then jq -n --arg c \"$out\" '{hookSpecificOutput:{hookEventName:\"SessionStart\",additionalContext:$c}}'; fi",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Merge this into the existing `~/.claude/settings.json` hooks rather than replacing other settings. Adjust the command path for a custom installation and ensure the hook inherits `CORTEX_HOME`.

`--weekly` records a timestamp in `<state-dir>/cortex-doctor-last-run` and stays silent inside its seven-day gate. Remove that marker to force the next weekly check. `--no-probe` skips advisor CLI execution. Ordinary `doctor` can run CLI version checks; `doctor --deep-probe` makes real prompt calls and can spend tokens, so use it only when authorized.

## Troubleshooting

**The agent does not declare a route, or no route appears in history.** Confirm that a fresh session loads the canonical `cortex.md` through the host's instruction mechanism. Ask the agent which protocol it loaded and which CLI path it will use. `doctor --no-probe` can check setup drift, but it cannot prove that the host loaded an instruction. Genuine trivia may skip routing. For a non-trivial task, confirm that the agent actually ran `log-line` and inspect its command output.

**History or hints are empty.** A new installation reports no routes until a task has been logged. A class or tier filter may also produce no matches. This is expected output, not a failed installation. If a command exits with an error, inspect that error and the selected state path before repeating a write.

**The log seems to be in the wrong place.** Compare `CORTEX_HOME` and `CLAUDE_DIR` in the shell and agent environment. A one-shot installer override does not persist. Use the same exported root and its installed executable, and make sure the host reads that root's `cortex.md`. Existing histories are not automatically merged when you change state directories.

**Installation stops on a skill conflict or symlink.** The installer refuses personalized skills and linked destinations before writing files. Preserve your customization and merge the reported skill manually. Review a linked path's target and choose an ordinary installation directory if appropriate. Do not delete a personalized registry or skill just to silence the conflict.

## Related setup

- [Build a registry](registry.md) from tools available in your session.
- [CLI reference](cli.md) for daily use and audits.
- [Optional Jev adviser](jev-adviser.md), off by default, with a separate setup and rollback procedure.
- [Frontend Design Library](../frontend/README.md), a separate resource library with its own `scripts/install_frontend_library.sh` installer. Its installer leaves the Cortex CLI and routing configuration intact.
