# Update, pin or remove Cortex

The installer copies files into an agent home; the checkout and installed files are separate. Your personalized registry and history are local state. Keep them through updates and removal unless you explicitly want to discard them.

## Pin a reviewed version

Use a clean checkout for a reproducible installation. Inspect [releases](https://github.com/amitvijapur/cortex/releases), choose a published tag and read its notes before checking it out. Do not assume a planned version exists. For example, after replacing `PUBLISHED_TAG` with an actual reviewed tag:

```bash
git clone https://github.com/amitvijapur/cortex.git cortex-pinned
cd cortex-pinned
git fetch --tags origin
git checkout --detach PUBLISHED_TAG
git rev-parse HEAD
```

Record the commit ID with your installation notes. Checking out a tag pins the copied source; the installer does not establish a package-manager update channel.

## Back up before updating

Resolve the same state root used by the running agent:

```bash
cortex_state_dir="${CORTEX_HOME:-${CLAUDE_DIR:-$HOME/.claude}}"
cortex_backup_dir="$HOME/cortex-backups/$(date +%Y%m%dT%H%M%S)"
mkdir -p "$cortex_backup_dir"
```

Copy the files you use into that backup, preserving paths so you can restore them. Inspect first, especially when your root is also an agent home. Include:

- `cortex.md`, any pending `.new` or generated version, and `cortex-log.jsonl`.
- Cortex CLI modules under `bin/` and Cortex-owned skill directories, including `.cortex-installed.sha256` stamps.
- Cortex proposals, inventory and optional evidence or experiment files you want to retain.
- Host instructions and any settings files containing Cortex imports, environment configuration or optional hooks.

Also back up optional skill copies in your Codex home and `~/.agents/skills/` when present. This backup can contain private task history; keep it private. Do not copy your entire agent home into the public repository.

## Install and merge the update

From the clean checkout of your chosen revision:

```bash
export CORTEX_HOME="$cortex_state_dir"
./install.sh
```

The installer refreshes the CLI and recognized unmodified skills. It refuses linked destinations and personalized skill conflicts before copying. Review a conflict and merge it manually; preserve custom content.

An existing `cortex.md` stays in place and the new template becomes `cortex.md.new`. Compare them:

```bash
diff -u "$CORTEX_HOME/cortex.md" "$CORTEX_HOME/cortex.md.new"
```

`diff` returns status 1 when files differ. Review framework changes and merge what applies, preserving your actual workflows, shortcuts and custom paths. Recheck any host instructions containing a copied protocol. The installer does not merge these files for you. If you use `/cortex-init`, review its proposed registry diff separately.

Verify the installed revision and rerun the [first-task acceptance check](first-run.md#4-run-a-real-task-and-inspect-the-record):

```bash
cmp bin/cortex "$CORTEX_HOME/bin/cortex"
python3 "$CORTEX_HOME/bin/cortex" doctor --no-probe
```

To roll back, restore the backed-up Cortex files and host edits, or reinstall the previous reviewed revision and restore your previous registry. Preserve the accumulated log and other history. Restoring an old log would lose events recorded since the backup.

## Remove Cortex without removing your agent setup

There is no automatic uninstaller. Back up first, then inspect and remove only the Cortex-owned changes below:

1. Remove the Cortex import or routing block you added to `CLAUDE.md`, `AGENTS.md` or another host's rules. Preserve every unrelated instruction. Check global and project scopes, including copied protocol text.
2. Remove optional Cortex `SessionStart` hook entries and Cortex-specific environment settings, shell aliases or functions. The installer adds no hook itself. Keep unrelated JSON settings and hooks. If you enabled the optional adviser or intake service, follow that feature's separate shutdown instructions before removing its files.
3. Inspect the chosen state's `bin/cortex`, `bin/cortex_jev.py` and `bin/cortex_skill_evidence.py`, then remove those files if they still belong to this installation.
4. Inspect Cortex skill directories before removal. The primary state root may contain `cortex-log`, `cortex-learn`, `cortex-reroute` and `cortex-init`; an existing Codex home may contain log, learn, reroute and delegate; `~/.agents/skills/` may contain log, learn and reroute. Remove only Cortex-owned skill files and stamps. Preserve custom or shared content and directories containing anything else.
5. Keep `cortex.md`, `cortex-log.jsonl`, backups, proposals, inventory and optional evidence/experiment history by default. You can archive them outside the active configuration directory. Inspect personal data before sharing any of it.
6. Start a fresh host session and confirm Cortex instructions, hooks and skills no longer activate. Confirm the rest of your agent setup still works.

Never delete `~/.claude`, `~/.codex`, `~/.agents` or a whole custom root to uninstall Cortex. The clone itself can be archived after checking for uncommitted work; removing it does not uninstall copied files.

## First release checklist

The initial packaging target is `v0.1.0`. A changelog entry or local tag is not proof of publication. Before publishing the release:

- Run `bash scripts/run_checks.sh` on the exact candidate commit from a fresh checkout. Record OS and Python versions and any untested combinations.
- Test install, re-install, conflict preservation and a root containing spaces in isolated temporary homes. Do not use personal state for fixtures.
- Review the [first-run guide](first-run.md), links and generated visuals. Perform a real host trial separately from CLI fixture tests.
- Confirm public assets and release files exclude personal logs, secrets and unrelated edits.
- Publish the tag and release notes only after review. Record the release URL and commit ID, then repeat the documented pinned-checkout path against the published tag.

[Contributing](../CONTRIBUTING.md) covers the default no-model checks. [Adoption feedback](adoption-feedback.md) tracks what external trials still need to establish.
