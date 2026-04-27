# Cortex

> **Meta-router for Claude Code.** Sits above every workflow system in your stack and decides — per task — which system, which specialist, which effort tier.

```
                          [ Task Arrives ]
                                  v
                       +---------------------+
                       |  Routing Protocol   |
                       |   1. Classify       |
                       |   2. Calibrate      |
                       |   3. Route          |
                       |   4. Specialise     |
                       |   5. Execute + Log  |
                       +----------+----------+
                                  v
        +----------+----------+-------------+----------+----------+
   Orchestrators  Specialists  Domain Models  Quality  Infrastructure
   (OMC,GSD,ECC)  (180+ agents) (Kronos, ...)  (Adv.)  (MCPs, etc.)
```

Cortex doesn't replace your workflow systems. It picks between them, attaches the right specialist, and learns from every decision.

---

## Why this exists

Multi-LLM voting (Karpathy's LLM Council, OpenRouter consensus, etc.) is a clean primitive. But after running my own version daily for months, I've come to believe it's **one tool, not the system**.

Routing is the harder problem.

When a task lands, "which LLM should debate this?" is rarely the right question. The right questions are:

- What *kind* of work is this? (build / review / plan / research / debug / design)
- What *effort tier* does it deserve? (L1 reflex -> L4 max-thoroughness)
- Which *workflow system* owns this shape? (multi-agent orchestrator? phase-based PM? PR pipeline? knowledge graph?)
- Which *specialist* should drive? (Backend Architect != Security Engineer != Voice AI)
- Should I *fan out* to parallel specialists with a reconciler?
- Should I *trigger* a multi-LLM council (only some tasks deserve it)?

Cortex answers all of these before any model touches the task.

---

## Install

Requires Claude Code with `~/.claude/` set up. Tested on macOS + Linux.

```bash
git clone https://github.com/amitvijapur/cortex.git
cd cortex
./install.sh
```

Then add `@cortex.md` to your global instructions so it loads in every session:

```bash
echo '@cortex.md' >> ~/.claude/CLAUDE.md
```

That's it. Try it:

```bash
python3 ~/.claude/bin/cortex doctor
python3 ~/.claude/bin/cortex --help
```

The installer copies:
- `bin/cortex` — the routing log + self-learning CLI
- `skills/cortex-log`, `skills/cortex-learn`, `skills/cortex-reroute` — slash commands inside Claude Code
- `templates/cortex.md` -> `~/.claude/cortex.md` (only if not already present)

It does **not** modify `~/.claude/settings.json`. The optional SessionStart hook is opt-in — see [Optional: SessionStart hook](#optional-sessionstart-hook).

---

## The Routing Protocol

Every non-trivial task goes through 5 steps:

| # | Step | What it produces |
|---|---|---|
| 1 | **Classify** | One of: build / review / plan / research / debug / design / quickfix |
| 2 | **Calibrate** | Effort tier L1 / L2 / L3 / L4 |
| 3 | **Route** | Workflow system (your registry) |
| 4 | **Specialise** | Agent(s), with parallel fan-out for cross-domain work |
| 5 | **Execute + Log** | Run the route. Log the decision with reasoning. |

L1 trivia (one-line edits, lookups, casual questions) skips the protocol — no point routing them.

The output is always a single line:

```
OMC > ralplan > Backend Architect @ L3
```

Cortex declares this *before* execution. If you disagree, redirect with `/cortex-reroute "Direct > batched-edits @ L2"` and Cortex marks the original as corrected — that becomes training signal.

---

## The Tier System (L1-L4)

Default tier is **L2**. Heuristics push up or down:

| Tier | When | Pattern | Verify |
|---|---|---|---|
| **L1** | Reversible local edit, clear scope | Direct execution | Trust |
| **L2** | Standard task, single domain | Single specialist + autopilot | Spot-check |
| **L3** | Touches prod / shared infra / high stakes / cross-domain | Plan-and-verify loop | Verifier pass |
| **L4** | Cannot fail (migrations, security, money) | Iterate-until-verified, parallel team | Full verify loop |

The biggest single calibration trigger is **Domain breadth**:
- Single domain -> one specialist
- 2+ independent disciplines (backend + frontend + auth, security + perf + a11y) -> **parallel specialists + a reconciler**

Multi-agent fan-out is the *correct* shape for cross-domain work, not an upgrade. Don't wait to be asked.

---

## CCG auto-fires

CCG = Claude + Codex + Gemini tri-model council. The "LLM Council" pattern, packaged as one tool inside Cortex.

It fires automatically on:

- **Pre-plan check** for L3/L4 work — catches single-model blind spots before execution
- **Irreversible actions** — migrations, prod pushes, force-pushes, payments
- **User uncertainty signals** — "not sure", "what do you think", "am I missing something"
- **High-stakes reconciler** — replaces single-agent reconciler in customer-facing fan-outs
- **Security audits** — runs *before* the single Security Engineer deep dive

CCG is skipped on L1/L2 routine work. It costs real tokens; reserve it for decisions where cross-validation pays for itself.

This is the mechanism through which the Karpathy primitive lives inside the system — but only as one of many possible answers to "what should we do here?"

---

## Self-Learning Loop

Cortex logs every routing decision to `~/.claude/cortex-log.jsonl`:

```json
{
  "ts": "2026-04-26T18:14:06Z",
  "task": "Build dashboard AI agent...",
  "class": "build",
  "system": "OMC",
  "pattern": "autopilot",
  "agent": "AI Engineer",
  "tier": "L3",
  "tier_reason": "Multi-phase build, security-critical",
  "system_reason": "Plan already CCG-revised, AI Engineer is the right specialist"
}
```

The log accumulates as a byproduct of routing. Phases activate automatically:

| Phase | Trigger | What happens |
|---|---|---|
| **1 - Visibility** | active from day 1 | Every route logged with reasoning |
| **2 - Pattern surfacing** | ~20 routes | `/cortex-learn` detects repeating tuples and writes proposals |
| **3 - Similarity bias** | ~200 routes | Hash the task and bias toward what worked before. *Not built yet.* |
| **4 - Correction capture** | active from day 1 | `/cortex-reroute` marks last route as corrected — highest-quality training signal |

**Approve, don't auto-apply.** The learning layer proposes; you decide. No silent edits to `cortex.md`.

---

## Slash commands

| Command | What it does |
|---|---|
| `/cortex-log` | Show last 20 routes with full reasoning. Pass `--project X` to filter |
| `/cortex-learn` | Detect repeating patterns, write markdown proposals |
| `/cortex-learn --check` | Terse session-start check — one line if drift exists |
| `/cortex-reroute "new route"` | Mark last route as corrected |
| `cortex doctor` | Audit setup for drift between docs, skills, and log |
| `cortex log-line "OMC > ralplan > Backend Architect @ L3" "task description" --class build` | Log a route from the natural routing line |

---

## Populating Your Registry

The shipped `cortex.md` is a **framework**, not a config. The Workflow Registry section is intentionally sparse — only OMC is filled in as a worked example.

You add your own systems. Examples of what to register:

- **Orchestrators** — OMC, GSD, ECC, your own multi-agent framework
- **Specialists** — Agency Agents, custom subagents, framework-specific skills
- **Domain models** — domain-specific foundation models you've installed (financial, scientific, etc.)
- **Quality gates** — Adversarial Spec, security review tools
- **Infrastructure** — Graphify, Context7, Exa, Firecrawl, MCP servers

For each, document:
1. Name + codename
2. What it's good at (1 line)
3. Pattern table (when to use)

Add new ones with `"add X to Cortex"` — the framework expects you to grow it.

See [`examples/cortex.md`](examples/cortex.md) for a populated real-world version.

---

## Optional: SessionStart hook

For weekly self-audits surfaced inline at session start, add this to `~/.claude/settings.json`:

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

The script self-gates to fire at most once per 7 days. When it runs:
- All clean -> `[cortex] all green (32 routes, Phase 2)`
- Drift detected -> `[cortex] 5 warn, 0 fail — run cortex doctor for details`
- Within gate window -> silent, zero noise

State lives in `~/.claude/cortex-doctor-last-run`. Delete that file to force a fresh check next session.

---

## What's in the repo

```
cortex/
+- README.md              <- you're here
+- LICENSE                <- MIT
+- install.sh             <- copies files to ~/.claude/
+- bin/
|  +- cortex              <- Python CLI (log, show, learn, reroute, doctor, log-line)
+- skills/
|  +- cortex-log/SKILL.md
|  +- cortex-learn/SKILL.md
|  +- cortex-reroute/SKILL.md
+- templates/
|  +- cortex.md           <- framework with stub registry — installed as ~/.claude/cortex.md
+- examples/
|  +- cortex.md           <- populated example showing what a real config looks like
+- assets/
   +- cortex-flowchart.html      <- architecture diagram (open in browser)
   +- cortex-vs-council.html     <- side-by-side comparison: LLM Council vs Cortex
```

---

## License

MIT. Use it, fork it, build something better.

---

## Credits

Built on top of (and routes between) tools by many builders.

Inspired by, and a friendly response to, [Andrej Karpathy's LLM Council](https://github.com/karpathy/llm-council). His pattern is the primitive. This is the layer above.
