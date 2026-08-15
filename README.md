<div align="center">

<img src="assets/cortex-logo.png" alt="Cortex logo" width="130" />

# Cortex

**A meta-router for coding agents.** It sits above every workflow system in your stack and decides, per task, which system runs, which specialist drives, and how much effort the work deserves. Then it logs the decision, learns from the outcome, and ships the checks that tell you whether any of that is actually happening.

<sub>Built for **Claude Code** · runs on **Cursor, Codex, Gemini CLI, Aider & Windsurf** too. [See how ↓](#using-cortex-with-other-agents)</sub>

<img src="assets/cortex-hero.png" alt="Cortex routes each task to the right system" width="820" />

[![built for Claude Code](https://img.shields.io/badge/built%20for-Claude%20Code-2c5282?style=flat-square)](https://claude.com/claude-code)
&nbsp;![works with any coding agent](https://img.shields.io/badge/also_runs_on-Cursor%20·%20Codex%20·%20Gemini%20·%20Aider-2f855a?style=flat-square)
&nbsp;![effort L1–L4](https://img.shields.io/badge/effort-L1%E2%80%93L4-4a9eff?style=flat-square)
&nbsp;![self-learning loop](https://img.shields.io/badge/self--learning-loop-63b3ed?style=flat-square)
&nbsp;![license MIT](https://img.shields.io/badge/license-MIT-64748b?style=flat-square)

</div>

<p align="center"><img src="assets/stack-overview.svg" alt="A task enters the routing protocol and is dispatched to orchestrators, specialists, quality gates, domain models, or infrastructure" width="880"></p>

Cortex does not replace your workflow systems. It picks between them, attaches a specialist, declares the reasoning before execution, and records the outcome.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Install](#install)
- [What it costs you in context](#what-it-costs-you-in-context)
- [Using Cortex with other agents](#using-cortex-with-other-agents)
- [How it works](#how-it-works)
- [The self-learning loop](#the-self-learning-loop)
- [Checking the router](#checking-the-router)
- [CLI reference](#cli-reference)
- [The stack Cortex routes between](#the-stack-cortex-routes-between)
- [Building your own registry](#building-your-own-registry)
- [Repo layout](#repo-layout)
- [Credits](#credits)

---

## Why this exists

An agent with many tools available makes the same decision repeatedly, and usually badly: which tool, at what effort, with which specialist. That decision is normally implicit, unlogged, and impossible to audit.

Multi-model voting answers a narrower question, which is how to check a single answer. It does not decide whether the task needed three models, a phase-based planner, or a one-line edit.

Cortex answers four questions before any model touches the work:

- What **kind** of work is this, and what **effort tier** does it deserve? A one-line fix and a payments migration should not get the same machinery.
- Which **workflow system** owns this shape, and which **specialist** drives?
- Does it span enough independent disciplines to need **parallel specialists**?
- Does it need a **multi-model council** at all? Most tasks do not.

Every decision is logged with its reasoning and, when the task ends, its outcome. That log surfaces repeating patterns, weights future routes toward what shipped, and exposes where effort is being overspent.

---

## Install

<p align="center"><img src="assets/cortex-setup.svg" alt="Cortex setup flow: clone, install, discover your systems, interview, your registry, route" width="880"></p>

Requires [Claude Code](https://claude.com/claude-code) with a `~/.claude/` directory, and Python 3. Tested on macOS and Linux. Using Cursor, Codex, Gemini CLI, Aider or Windsurf instead? [See below](#using-cortex-with-other-agents).

```bash
git clone https://github.com/amitvijapur/cortex.git
cd cortex
./install.sh
echo '@cortex.md' >> ~/.claude/CLAUDE.md   # load Cortex every session
```

Then run **`/cortex-init`**. It scans what you already run (agents, skills, MCP servers, CLIs, other-agent configs), interviews you on anything ambiguous, and writes your Workflow Registry. It never overwrites `cortex.md` without a backup and your confirmation.

Verify with `python3 ~/.claude/bin/cortex doctor`.

| The installer copies | To |
|---|---|
| `bin/cortex` | `~/.claude/bin/cortex` |
| `skills/cortex-log`, `cortex-learn`, `cortex-reroute`, `cortex-init` | `~/.claude/skills/` |
| `templates/cortex.md` | `~/.claude/cortex.md`, only if you don't already have one |

It does not touch `settings.json`.

<details>
<summary><b>Optional: a self-audit at session start</b></summary>

<br>

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "out=$(python3 ~/.claude/bin/cortex doctor --weekly 2>/dev/null); if [ -n \"$out\" ]; then jq -n --arg c \"$out\" '{hookSpecificOutput:{hookEventName:\"SessionStart\",additionalContext:$c}}'; fi",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

It fires at most once every 7 days: `[cortex] all green (73 routes, Phase 3)`, or `[cortex] 5 warn, 0 fail`, or silence inside the gate window. State lives in `~/.claude/cortex-doctor-last-run`; delete it to force a check.

</details>

---

## What it costs you in context

Cortex loads every session, so it is worth knowing the bill.

The shipped `templates/cortex.md` is **about 6,000 tokens** and does not grow on its own. What grows is the registry underneath it, and it grows unnoticed because nothing forces a review. One registry reached 19,000 tokens, at which point an audit found eight entries that had never been routed to across 154 logged decisions.

<p align="center"><img src="assets/context-cost.svg" alt="What loads before you type: the framework, your registry, and your agent roster, with cold registry detail lifting out to on-demand" width="880"></p>

**The rule that came out of that:** split the registry by temperature, in one specific place.

- **The Decision Shortcuts table stays loaded.** It is the index: one line per task type, naming the system and when to reach for it.
- **Per-system detail loads on demand.** Pattern tables, setup notes, caveats.

Splitting it the other way round fails in a specific way. Move the shortcut rows out and the router stops knowing the system exists, so it never routes there, so the entry looks unused, so it gets deleted.

The framework is rarely what dominates anyway. A few hundred agent and skill descriptions outweigh `cortex.md` several times over, so count those first.

---

## Using Cortex with other agents

Nothing here is Claude-specific. The framework is one Markdown file and the CLI is plain Python over a state directory. Set `CORTEX_HOME` to move that state anywhere (unset, it falls back to `~/.claude`):

```bash
export CORTEX_HOME="$HOME/.cortex"
```

Then load `cortex.md` into whatever your agent reads:

| Agent | Where the framework goes |
|---|---|
| **Claude Code** | `~/.claude/cortex.md`, referenced from `CLAUDE.md` with `@cortex.md` |
| **Codex CLI** (or any `AGENTS.md` tool) | paste into `AGENTS.md`, repo root or `~/.codex/AGENTS.md` |
| **Cursor** | `.cursor/rules/cortex.mdc`, or User Rules in Settings |
| **Gemini CLI** | append to `GEMINI.md` |
| **Windsurf** | `.windsurf/rules/cortex.md` |
| **Aider** | point `read:` in `.aider.conf.yml` at it |

Only two things are Claude Code conveniences: the slash-command skills (elsewhere, call `python3 bin/cortex …` directly) and the example registry, which you should swap for systems your agent can actually invoke.

---

## How it works

### The routing protocol

<p align="center"><img src="assets/routing-protocol.svg" alt="The routing protocol: classify, calibrate, hint, route, specialise, log, execute, outcome; outcomes feed future hints" width="880"></p>

Every non-trivial task produces a single declared line, printed **before** execution starts:

```
OMC > ralplan > Backend Architect @ L3
OMC > /team > [Frontend Developer ∥ Stripe skill ∥ Accessibility Auditor] → Software Architect reconciler @ L3
```

The line is declared before execution so it can be corrected. If the call looks wrong, `/cortex-reroute` records what was wanted instead, and that correction carries more signal than any other row in the log. L1 trivia skips all of this.

### The tier system

Tier is a **depth** decision: how much machinery does correctness actually require?

| Tier | Name | Model / effort | Thinking | Verification | Subagents |
|---|---|---|---|---|---|
| **L1** | Reflex | fast / cheap | none | trust it | 0 |
| **L2** | Standard | mid-tier, fast mode | think | spot-check | 0–1 |
| **L3** | Deep | frontier | think hard | verifier pass | 1–2 |
| **L4** | Max | frontier, max effort | ultrathink | full verify loop | parallel team |

<p align="center"><img src="assets/tier-ladder.svg" alt="Effort tiers L1 to L4, escalating from reflex to max rigor, with L2 as the default" width="820"></p>

**The default is L2.** Blast radius, ambiguity, stakes, novelty, reversibility and how certain you sounded push it up or down. Override in plain language: *"go light"* forces L1, *"be thorough"* L3, *"ultrathink"* L4, and *"bump it"* / *"drop it"* move one step.

### Calibration

Three rules do most of the work. The reasoning behind each is in **[docs/routing.md](docs/routing.md)**.

**High effort must justify itself against standard effort**, not the other way around. Picking L3 because work feels important is inflation. The route has to name a failure mode L2 would actually produce. In one audit, the first 36 logged routes came out at **67% L3**, and most of that was reflex.

**Depth and breadth are separate decisions.** Tier sets how much rigour a task gets. Shape sets how many independent disciplines it touches. Two or more disciplines means parallel specialists and a reconciler, at whatever tier the work warrants. Running a cross-domain task through one generalist is a routing bug, not a saving.

**Confidence is recorded as three values, not one.** Picking the right system, picking the right tier, and understanding the request all fail independently. The strongest trigger in the system is high confidence on the first two and low on the third, which is the state where an agent knows exactly which tool to use and builds the wrong thing with it.

[CCG](docs/routing.md#ccg-the-council-as-one-tool), a tri-model council of Claude, Codex and Gemini, is one tool the router reaches for on irreversible actions, security audits, and any sign of user uncertainty. It is not a default, because three models cost three models' worth of tokens.

---

## The self-learning loop

Every route is appended to `~/.claude/cortex-log.jsonl` as a byproduct of working. No ceremony, no retros.

The log is **append-only**. A route writes one line; the outcome is a *second* line referencing the first by id. The original row's bytes are never touched.

```jsonc
// written when the routing line is declared
{"event": "route", "event_id": "ev_7a8d080fc1f5", "task": "Refactor auth middleware",
 "class": "build", "system": "OMC", "pattern": "ralplan", "tier": "L3",
 "tier_reason": "Touches auth; L2 would skip the verifier pass",
 "route_confidence": "high", "tier_confidence": "med", "spec_confidence": "high"}

// appended when the task ends: a separate line, pointing back at the route
{"event": "outcome", "event_id": "ev_3a664b902d4d", "ref": "ev_7a8d080fc1f5",
 "outcome": "shipped"}
```

<p align="center"><img src="assets/append-only-log.svg" alt="Three log lines for one route: the original route, an outcome, and a correction, collapsed into a derived current view" width="880"></p>

Corrections work the same way, so a route's current state is *derived* by replaying its events, and `cortex history <event_id>` prints the chain. Overwriting the original row would leave only the final decision on record, not what the router first proposed. The difference between those two is what the learning layer reads.

<p align="center"><img src="assets/self-learning.svg" alt="The self-learning loop: route, execute, outcome, log, hint; every task sharpens the next route" width="880"></p>

Phases activate on data thresholds, not on a calendar. All four are active:

| Phase | Trigger | What it does |
|---|---|---|
| **1 · Visibility** | day one | Every route logged with full reasoning. `/cortex-log` replays it. |
| **2 · Pattern surfacing** | ~20 routes | `cortex learn` finds `(class, system, pattern)` tuples repeating ≥3× and proposes them as shortcuts. |
| **3 · Similarity bias** | ~40+ routes | `cortex hint` surfaces similar past routes scored by outcome. **Advisory: it informs the call, it does not make it.** |
| **4 · Outcome capture** | day one | Correction triggers append an event linking the replacement, leaving the original decision on the record. |

Two rules hold it together. **Approve, don't auto-apply**: the learning layer proposes and you dispose, because a router that rewrites its own rules without asking is one you cannot trust. **Correction beats prediction**: a negative hint score means past attempts at that route failed, which beats any similarity heuristic because it is ground truth you gave it.

---

## Checking the router

A declared routing line is generated text, so it can stay articulate while the behaviour underneath drifts. `eval/` measures the difference between what the protocol says and what the router does.

<p align="center"><img src="assets/evidence-layer.svg" alt="An append-only log read by three independent checks, each returning a verdict, with failures feeding back as fixes" width="880"></p>

**Adherence scoring.** The protocol says to declare a tier, run `hint` before routing, and record an outcome. `score_adherence.py --check` scores the log against floors in [`eval/adherence-thresholds.json`](eval/adherence-thresholds.json) and exits non-zero on a breach.

**Routing consistency.** `route_eval.py` puts a task to a headless session and asserts a property of the routing line that comes back:

| Kind | What it proves |
|---|---|
| `canary` | Only recall. The answer sits in `cortex.md` where the model can see it. Catches a protocol that stopped loading. |
| `rule` | Generalisation. A rule applied to a task the document has never seen. |
| `paired` | A directional property, comparing a transformed task against its own base rather than an absolute tier. |
| `shape` | Whether the fan-out heuristic fires at all. |

Paired cases always get their own session, because an earlier answer in a shared one anchors a later answer, which is exactly what a paired comparison must not allow. `CORTEX_HOME` is redirected to a sandbox so a model dutifully following the protocol cannot append test routes into the real log.

**Retrieval evaluation.** Agent selection is scored on a sealed train/test split, with hard negatives drawn from the same division as the target. Random negatives flatter retrieval, since telling a security agent from a marketing agent is trivial; same-division confusion is where it actually fails.

### The limits

These tests answer *"did something break?"*, not *"was that a good route?"* There is no oracle for routing quality here. The floors are targets rather than pre-registrations too, since they were set with the current numbers already visible.

The harness has rejected two changes that were already built: a BM25F ranker that won on the development set and lost on held-out data, and a confinement layer that defended against an adversary that does not exist for a personal tool. **[The full accounting](docs/evaluation.md).**

---

## CLI reference

```bash
# Log a route, natural form, straight from the declared routing line
cortex log-line "OMC > ralplan > Backend Architect @ L3" "refactor auth middleware" \
  --class build --tier-reason "touches auth; L2 would skip the verifier pass" \
  --route-confidence high --tier-confidence med --spec-confidence high

# What happened last time on something like this?
cortex hint "refactor the session store" --class build
cortex hint "..." --min-similarity 0.05 --top 10     # widen the net

# Close the loop
cortex outcome shipped
cortex outcome partial --note "stopped at the migration step"
cortex reroute --to "Direct > batched-edits @ L2"

# Review and audit
cortex show --project cortex        # last 20 routes with reasoning
cortex history <event_id>           # one route's correction chain, oldest first
cortex learn                        # detect repeating patterns, write proposals
cortex audit-tiers --tier L3        # every L3: was it really an L3?
cortex doctor                       # drift between docs, skills, and log
```

The checks live in [`eval/`](eval/) rather than the CLI:

```bash
python3 eval/score_adherence.py --check   # score the log against its floors
python3 eval/route_eval.py --dry-run      # list consistency cases, spend nothing
python3 eval/test_cortex_cli.py           # behavioural tests for the CLI
```

Everything degrades gracefully on an empty log. A fresh install says there is nothing to report rather than crashing.

**Slash commands** in Claude Code: `/cortex-log` (recent routes with reasoning), `/cortex-learn` (detect patterns, write proposals), `/cortex-learn --check` (one line, silent if nothing pending), `/cortex-reroute "new route"`.

---

## The stack Cortex routes between

Cortex is only as good as the registry underneath it. Mine is below, not because you should install all of it, but to show what a populated registry looks like and to credit the people whose work it routes between.

<details>
<summary><b>The full registry (30+ tools)</b></summary>

<br>

**Orchestrators**: the systems that actually run multi-step work.

| Tool | What it's for |
|---|---|
| [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | Multi-agent orchestration. Ships `ralplan`, `autopilot`, `ralph`, `/team`, and `/ccg`. The default for non-trivial builds. |
| [GSD (gsd-core)](https://github.com/open-gsd/gsd-core) | Spec-driven, phase-based project management with context-rot prevention. Best for long multi-phase builds. |
| [claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | Anthropic's official marketplace, `feature-dev`, `code-review`, `pr-review-toolkit`, `security-guidance`. |

**Quality gates**: the things that argue with your work before it ships.

| Tool | What it's for |
|---|---|
| [LLM Council](https://github.com/karpathy/llm-council) | Multiple models answer, cross-review, and a chairman synthesizes. The pattern CCG implements. |
| [adversarial-spec](https://github.com/zscole/adversarial-spec) | Harden a spec or API contract by debating it across models until they converge. Runs *before* you build. |
| [gitleaks](https://github.com/gitleaks/gitleaks) | Deterministic secret scanner. Regex and entropy, no LLM, a reproducible pre-commit gate that never hallucinates. |
| [defending-code harness](https://github.com/anthropics/defending-code-reference-harness) | Anthropic's security harness: `/threat-model`, `/vuln-scan`, `/triage`, `/patch`. |

**Knowledge and search**: what the router reads before it decides.

| Tool | What it's for |
|---|---|
| [Graphify](https://github.com/Graphify-Labs/graphify) | Turns code, docs, papers, and media into a queryable knowledge graph. Maps *meaning*, across content you already own. |
| [Understand Anything](https://github.com/Egonex-AI/Understand-Anything) | Code-only codebase knowledge graph with architecture tours and business-domain mapping. |
| [claude-mem](https://github.com/thedotmack/claude-mem) | Cross-session memory, captures, compresses, and re-injects context. |
| [Context7](https://github.com/upstash/context7) | Live, version-specific library docs injected into context. Stops the model guessing at an API it half-remembers. |
| [Exa](https://github.com/exa-labs/exa-mcp-server) · [Firecrawl](https://github.com/mendableai/firecrawl-mcp-server) | AI-native web search, and full-page extraction to markdown. Exa finds, Firecrawl extracts. |
| [Scrapling](https://github.com/D4Vinci/Scrapling) | Adaptive scraper with anti-bot bypass, the fallback when Firecrawl hits a wall. |
| [last30days](https://github.com/mvanhorn/last30days-skill) | Recency research across Reddit, HN, X, YouTube. The complement to deep research. |

**Specialists and skills**: who actually does the work once routed.

| Tool | What it's for |
|---|---|
| [Agency Agents](https://github.com/msitarzewski/agency-agents) | 240+ domain specialists across 20+ divisions, engineering, security, design, finance, GIS, marketing, and more. The pool the router fans out across. |
| [anthropics/skills](https://github.com/anthropics/skills) | First-party document skills: `docx`, `pdf`, `pptx`, `xlsx`, plus `mcp-builder` and `skill-creator`. |
| [knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) | Anthropic's non-code plugins, data, legal, enterprise search, PM, marketing. |
| [claude-tag-plugins](https://github.com/anthropics/claude-tag-plugins) | Anthropic's SaaS connector plugins, Jira, Linear, Salesforce, HubSpot, Datadog. One plugin per service. |
| [financial-services](https://github.com/anthropics/financial-services) | DCF, LBO, comps, earnings analysis, pitch decks, with live Excel and PowerPoint integration. |
| [Tessl](https://tessl.io/) | Framework-specific skills, Next.js, React, Stripe, Three.js, modern Python. |
| [obsidian-skills](https://github.com/kepano/obsidian-skills) | Vault operations via the Obsidian CLI. Where build logs get written. |
| [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) | 58+ real `DESIGN.md` specs (Stripe, Linear, Vercel). Drop one in a project so the UI stops looking AI-generated. |
| [Hyperframes](https://github.com/heygen-com/hyperframes) | Write HTML, render deterministic MP4. Product tours, explainers, chart-race video. |

**Domain models**: where a generic LLM is simply the wrong instrument.

| Tool | What it's for |
|---|---|
| [Kronos](https://github.com/shiyu-coder/Kronos) | Foundation model for OHLCV candlestick forecasting, trained on 45+ exchanges. Use it as a feature, never as an oracle. |
| [QuantMind](https://github.com/LLMQuant/quant-mind) | Ingests financial research at scale, arXiv, SEC filings, news, into a structured, queryable knowledge base. |

**Infrastructure**: the plumbing the layers above consume.

| Tool | What it's for |
|---|---|
| [Morph](https://www.morphllm.com/) | Fast Apply edits and semantic code search. |
| [DuckDB MCP](https://github.com/motherduckdb/mcp-server-motherduck) | In-process OLAP, SQL straight over local Parquet, CSV, and JSON. |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Lighthouse, a11y audits, network debugging, screenshots. Visual QA. |
| [Toolport](https://github.com/tsouth89/toolport) | Local MCP gateway with lazy tool discovery, compact meta-tools instead of every server's full catalog. |

> **A note on GSD.** The original `gsd-build/get-shit-done` repo was archived in June 2026. Development continues at [`open-gsd/gsd-core`](https://github.com/open-gsd/gsd-core), a community fork, which is what current plugin releases treat as upstream. That is the link above. Check it out yourself before adopting it.

</details>

---

## Building your own registry

The shipped `templates/cortex.md` is a **framework, not a config**. Its registry is deliberately stubbed, with only OMC filled in as a worked example.

Run **`/cortex-init`** and Cortex discovers what you already run, interviews you on the ambiguous parts, and writes the registry for you. It adopts your stack rather than imposing one.

By hand, each system needs a name, one line on strengths, one line on what it's best for, and a pattern table saying *when* each command is the right call. Then add a row to **Decision Shortcuts**, the router's cheat sheet: task type → default route → default tier.

Adding a system later is a sentence. Say *"add X to Cortex"* and it gets an entry. See [`examples/cortex.md`](examples/cortex.md) for a populated version.

---

## Repo layout

```
cortex/
├── bin/cortex           ← the CLI: log, log-line, show, history, hint,
│                          outcome, learn, reroute, audit-tiers, doctor, init
├── eval/                ← the checks: adherence scoring, routing-consistency
│   │                      replay, retrieval evaluation, CLI tests
│   ├── README.md        ← what each one does and does not establish
│   └── adherence-thresholds.json
├── docs/
│   ├── routing.md       ← calibration rules and the reasoning behind them
│   └── evaluation.md    ← what the checks prove, and what they have rejected
├── skills/              ← /cortex-log, /cortex-learn, /cortex-reroute, /cortex-init
├── templates/cortex.md  ← the framework, registry stubbed
├── examples/cortex.md   ← a populated registry, for reference
├── assets/              ← diagrams
└── install.sh
```

---

## Credits

Cortex decides and records. Nearly everything valuable in the stack above was built by someone else; Cortex chooses which of them to call and keeps the record of why. Credit to every maintainer in [that table](#the-stack-cortex-routes-between).

## License

MIT. Use it, fork it, build something better.
