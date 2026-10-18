# Your first routed task

Start with one real, bounded task. The acceptance check is that your agent loads the protocol, declares a proportional route, does the work and records its actual outcome. Cortex does not dispatch the workflow itself.

## 1. Install and choose one state root

On macOS or Linux, with Bash, Git and Python 3.11 or newer available:

```bash
git clone https://github.com/amitvijapur/cortex.git
cd cortex
export CORTEX_HOME="$HOME/.claude"
./install.sh
python3 "$CORTEX_HOME/bin/cortex" --help
```

Keep this checkout for updates. The default uses `~/.claude` even if your host is Codex. You may choose another ordinary directory, but keep the same `CORTEX_HOME` exported in the shell **and the agent's command environment**. State resolution is `CORTEX_HOME`, then `CLAUDE_DIR`, then `~/.claude`. [Installation details](setup.md#what-the-installer-changes) explain optional skill copies and conflict handling.

The export above lasts for this shell. If you start the agent elsewhere, configure its environment consistently or use an explicit `CORTEX_HOME` on each CLI invocation. A custom state root does not move the host's instruction files or make its skills discoverable automatically.

## 2. Activate your host

### Claude Code, guided setup

For the default root, add this line once to your existing `~/.claude/CLAUDE.md`, preserving its other content:

```text
@cortex.md
```

Claude Code supports file imports relative to the containing `CLAUDE.md`. For a custom Cortex root, import that root's `cortex.md` from the `CLAUDE.md` your host actually loads. See [Claude Code's instruction documentation](https://code.claude.com/docs/en/memory#import-additional-files). For import paths containing spaces, use the backslash-escaped syntax in that documentation; quoted import paths are not loaded. A custom installation may also need its setup skill exposed through your host's supported skill mechanism; the default installation is the simplest guided path.

Start a fresh session and run:

```text
/cortex-init
```

Ask it to start with Direct execution if you have no other workflows. The skill scans local tools, proposes a registry, backs up existing configuration and asks you to review the merge before writing. Detection does not prove session access. Verify every proposed tool is callable. `cortex init` alone only writes a discovery inventory.

### Codex, manual setup

Codex loads `AGENTS.md` instructions. Merge the following into the **project's existing `AGENTS.md`** for a first project-scoped trial. Replace `/absolute/path/to/state` with the expanded absolute value of your chosen `CORTEX_HOME`, not a literal placeholder. Preserve existing instructions and check whether an `AGENTS.override.md` takes precedence. [Codex instruction discovery](https://developers.openai.com/codex/guides/agents-md) describes scope and precedence.

```markdown
## Cortex routing

Before non-trivial tasks, read and follow /absolute/path/to/state/cortex.md.
Use CORTEX_HOME=/absolute/path/to/state for every Cortex CLI command and invoke
Python 3 with /absolute/path/to/state/bin/cortex. Keep paths quoted in shell commands.
Declare and log the chosen workflow and effort tier before work, then record the
actual outcome. Use only capabilities exposed in this session. Existing project
instructions and permissions still apply. Trivial tasks may skip routing.
```

This asks Codex to read the canonical file. It is not an `@file` import. Alternatively, merge the full reviewed protocol into the applicable `AGENTS.md`, keeping one authoritative registry and updating both copies when needed.

Next, read the installed `cortex.md` and [minimal registry excerpt](../examples/minimal-registry.md). Back up `cortex.md`, then merge its Direct workflow and shortcuts after reviewing the diff. Preserve the framework and real existing workflows. Remove unavailable sample routes. For a custom root, update framework CLI references too. Start a fresh Codex session and ask it to identify the canonical file, selected root and callable workflows before the trial.

The installer copies maintenance and delegation skills into an existing Codex home. It does not provide the guided `/cortex-init` skill there. The manual path above does not depend on those skills.

### Other hosts

Use the [manual host integration table](setup.md#other-agents) to load the reviewed protocol through that host's instruction mechanism. Merge the same minimal registry and verify the root and available capabilities in a fresh session. These are manual adaptation paths, not a claim of identical host behavior or a completed live compatibility matrix.

## 3. Check the installation

In the same environment the agent will use:

```bash
python3 "$CORTEX_HOME/bin/cortex" doctor --no-probe
python3 "$CORTEX_HOME/bin/cortex" show --last 3
```

An empty history is expected before the first task. Read and resolve reported failures; inspect warnings rather than installing tools just to silence them. `doctor` checks files and configuration, not whether your host loaded the protocol. `--no-probe` avoids adviser CLI execution. Do not use `--deep-probe` for this trial.

## 4. Run a real task and inspect the record

Open a small project with a README and give the agent this bounded request:

```text
Follow Cortex. Review this project's README setup instructions against the files
and commands in the repository. Report up to three concrete mismatches with file
evidence, or explain what you checked if you find none. Do not edit files, install
anything, call paid advisers or run commands that change project or service state.
Use only current session capabilities. Declare and log the route before the review,
then record the actual outcome when the review is complete.
```

Check the following:

- The agent names the canonical protocol file and uses your selected state root.
- Before reviewing, it retrieves hints, declares a route and reason, and logs it. A new history can have no hints. `Direct > bounded-review @ L2` is a suitable route for this scope, not a required exact answer.
- The report cites inspected files and describes the checks performed. Finding no mismatch can be a valid review result.
- The agent records an outcome only after doing the work. `partial` is appropriate if it cannot finish. `shipped` means this review was completed, not that software was deployed.

Then inspect the local record:

```bash
python3 "$CORTEX_HOME/bin/cortex" show --last 3
```

Match the task, route, tier and outcome to the actual session. If the CLI cannot identify the route for an outcome, have the agent inspect its route event and use that exact ID with `outcome --ref`; do not attach the result to an unrelated route. [CLI reference](cli.md#record-outcomes-and-corrections).

If no route appears, check the protocol read, CLI errors and state root before repeating a write. Keep your terminal output and follow the [feedback checklist](adoption-feedback.md) if you get stuck. A successful trial demonstrates your setup for this task; it does not prove general routing quality or savings.
