# Cortex — Workflow Routing Layer

> Meta-router that sits above all workflow systems. Loaded globally across all projects.
> When you install a new workflow system, add it here with `"add X to Cortex"`.

---

## Routing Protocol

Before starting any non-trivial task:

1. **Classify** — build / review / plan / research / debug / design / quick fix
2. **Calibrate** — pick effort tier (L1–L4) using heuristics in the Effort Calibration section
3. **Route** — pick the workflow system from the registry below
4. **Specialise** — pick the pattern + agent(s). **Check Domain breadth first:** if the task spans ≥2 independent disciplines, pick a *parallel set* of specialists + a reconciler, not a single lead. Single-agent is the exception for cross-domain work, not the default.
5. **State + Log** — one line: `[System] > [Pattern] > [Agent(s)] @ [Tier]` (fan-outs render as `[Agent A ∥ Agent B] → Reconciler`), then execute and log via `cortex log` or `cortex log-line`
6. **Skip** — for quick lookups, file reads, casual questions, single-line edits (no calibration, no state line, no log)

---

## Effort Calibration

Claude auto-picks a tier using the heuristics below and **declares it in the routing line** before execution. You can override upfront or redirect after seeing the declaration.

**Default tier is L2.** Only change when heuristics push up or down.

### Tiers

| Tier | Name | Model | Thinking | Pattern | Verify | Subagents |
|------|------|-------|----------|---------|--------|-----------|
| **L1** | Reflex | haiku / sonnet | none | direct | trust | 0 |
| **L2** | Standard | sonnet | think | autopilot / single specialist | spot-check | 0–1 |
| **L3** | Deep | opus | think hard | plan-and-verify | verifier pass | 1–2 |
| **L4** | Max | opus | ultrathink | iterate-until-verified | full verify loop | parallel team |

### Calibration heuristics (pick the highest that applies)

- **Blast radius** — reversible local edit → L1/L2; touches prod, migrations, shared infra, auth → L3/L4
- **Ambiguity** — clear one-liner → L1/L2; fuzzy spec → L3 + clarifying interview first
- **Stakes** — throwaway / personal → L1/L2; customer-facing, money, or security → L3/L4
- **Novelty** — familiar pattern → L2; new framework / unfamiliar SDK → L3 + docs lookup
- **Reversibility** — can undo with one command → drop a tier; can't → bump a tier
- **User signal** — uncertain or exploratory tone → bump a tier; decisive and scoped → keep or drop
- **Domain breadth** — **single domain** → one specialist (default); **≥2 independent domains** (e.g., backend + frontend, infra + security, design + copy + a11y) → **fan out to parallel specialists + a reconciler**, bump to L3 minimum. This is the primary trigger for multi-agent — don't wait to be asked. If the task touches two disciplines that would normally be owned by different humans, it's multi-agent by default.

### Override phrases

| Phrase | Effect |
|--------|--------|
| `"go light"` / `"quick and dirty"` / `"cheap it"` | Force L1 |
| `"standard"` / `"normal"` | Force L2 |
| `"be thorough"` / `"do it properly"` | Force L3 |
| `"must be perfect"` / `"bulletproof"` | Force L4 |
| `"bump it"` | Raise one tier |
| `"drop it"` | Lower one tier |

### Rules

- **L1 tasks skip the full routing protocol** — don't calibrate trivia, just do them
- **Tier is declared out loud before execution** — silent calibration breaks course-correction
- **One tier per task** — don't re-calibrate mid-flow unless something goes sideways (then stop, re-plan, re-state)
- **Don't inflate** — L3 and L4 cost real tokens; reserve L4 for things that genuinely can't break
- **Multi-agent is not inflation** — if *Domain breadth* fires (≥2 independent disciplines), parallel specialists is the *correct* shape, not an upgrade. Single-agent on a cross-domain task is a routing bug.

### CCG auto-fires

CCG = Claude + Codex + Gemini tri-model council. The "LLM Council" pattern, packaged as one tool. Fire it automatically, no asking, when:

- **Before committing an L3/L4 plan** — catches single-model blind spots before execution begins
- **Before irreversible actions** — migrations, prod pushes, force-pushes, destructive DB changes, auth/session rewrites, payment integrations
- **When the user signals uncertainty** — "not sure", "what do you think", "help me decide", "is this right", "am I missing something"
- **As the reconciler in high-stakes multi-agent fan-outs** — CCG's synthesis replaces single-agent reconcilers for L3+ fan-outs on customer-facing / money / security work
- **On security audits** — three-model pass (Codex for correctness, Gemini for attack surface, Claude for synthesis) runs *before* the single Security Engineer deep dive
- **When two prior outputs conflict** — instead of picking one, let CCG arbitrate with fresh framing

Skip CCG on L1/L2 routine work, quick fixes, well-known patterns, and anywhere the answer is obvious. CCG costs real tokens across 3 models — reserve it for decisions where cross-validation pays for itself.

When it fires, declare it in the routing line: `OMC > /ccg → ralplan > Backend Architect @ L3  [ccg=pre-plan-check]`.

### Worked examples

- `"rename this variable across the file"` → `Direct @ L1`
- `"add a loading state to this button"` → `OMC > autopilot > Frontend Developer @ L2`
- `"refactor the auth middleware to use the new session store"` → `OMC > ralplan > Backend Architect @ L3`
- `"migrate our payments from Stripe Charges to PaymentIntents in prod"` → `OMC > ralph > Security Engineer + Stripe skill @ L4`
- `"build a checkout page with Stripe, tracking, and a11y polish"` → `OMC > /team > [Frontend Developer ∥ Stripe skill ∥ Accessibility Auditor] → Software Architect reconciler @ L3  [breadth=frontend+payments+a11y]` — three independent domains, fan out by default
- `"audit this feature for security and performance"` → `OMC > /team > [Security Engineer ∥ Performance Benchmarker] → Critic reconciler @ L3  [breadth=security+perf]`

---

## Self-Learning Loop

Cortex logs every routing decision to `~/.claude/cortex-log.jsonl`, surfaces the reasoning trail on demand via `/cortex-log`, and detects repeating patterns via `/cortex-learn`. The log accumulates as a byproduct of normal routing, and learning activates automatically once data crosses thresholds.

### Log write (part of every routing protocol step 5)

After declaring the routing line, run this Bash call as an indivisible part of the State step.

**Form A — natural routing line (preferred):**

```bash
python3 ~/.claude/bin/cortex log-line \
  "<routing line, e.g. OMC > ralplan > Backend Architect @ L3>" \
  "<task description in 1 line>" \
  --class <build|review|plan|research|debug|design|quickfix> \
  --tier-reason "<heuristic that drove the tier>" \
  --system-reason "<why this system won over alternatives>"
```

**Form B — named flags (use for redirects or non-standard routes):**

```bash
python3 ~/.claude/bin/cortex log \
  --task "<task description>" \
  --class <class> \
  --system <system> \
  --pattern <pattern> \
  --agent "<agent>" \
  --tier <L1|L2|L3|L4> \
  --tier-reason "<...>" \
  --system-reason "<...>" \
  --redirect-from "<previous route, only when this is a correction>"
```

**Skip the log write for Skip-protocol tasks** (L1 trivia, file reads, lookups, casual questions). Log only routes that went through the full protocol.

### Phase progression (data-triggered, not calendar-triggered)

- **Phase 1 — Visibility (active now):** every route is logged. `/cortex-log` shows the last 20 with full reasoning.
- **Phase 2 — Pattern surfacing (activates at ~20 routes):** `/cortex-learn` detects `(class, system, pattern)` tuples that repeat ≥3 times and proposes them as Decision Shortcut candidates. The user approves, modifies, or dismisses.
- **Phase 3 — Similarity bias (activates at ~200 routes):** at route time, hash the task and check for similar past tasks. Bias the decision toward what worked before. *Not built yet.*
- **Phase 4 — Correction capture (active now):** when the user says `"reroute"` or `"actually use X"`, run `cortex reroute --to "..."`. The last log entry is marked corrected, and the next logged route gets `redirect_from` to link the correction.

### Commands

| Command | Purpose |
|---------|---------|
| `/cortex-log` | Show last 20 routes with full reasoning. Pass `--project X` to filter |
| `/cortex-learn` | Detect repeating patterns, write proposals |
| `/cortex-learn --check` | Terse session-start check — silent if no pending pattern |
| `/cortex-reroute "new route"` | Mark last route as corrected |
| `cortex doctor` | Audit cortex setup for drift between docs, skills, and log |

### Design principles

- **Visibility first, learning second.** The log is useful at T=0 (per-decision audit) and grows into a learning substrate.
- **Approve, don't auto-apply.** The learning layer proposes; you decide. No silent edits.
- **Data-triggered phases.** No calendar rituals, no monthly retros. Thresholds fire phases automatically.
- **Correction over prediction.** The highest-quality signal is the user saying "reroute" — explicit, unambiguous, ground truth.

---

## Workflow Registry

> **This is YOUR config.** The framework above is universal; the systems below are personal. Add the orchestrators, specialists, and tools you actually use.
>
> One example is filled in (OMC). The rest are stubs — replace with your stack.

### OMC (oh-my-claudecode)
**Installed:** Yes / No
**Strengths:** Multi-agent orchestration, verify/fix loops, parallel execution, team mode
**Best for:** Complex builds, planning, multi-step tasks needing quality gates, research

| Pattern | Use When |
|---------|----------|
| `ralplan "task"` | Important work needing planning + verify/fix loops. Default for non-trivial work. |
| `autopilot: task` | Well-defined, lower-risk tasks. One-shot autonomous. |
| `ralph: task` | Must be bulletproof. Won't stop until verified complete. |
| `/team N:executor "task"` | Parallel execution, multiple perspectives. |
| `/ccg` | Tri-model orchestration (Claude + Codex + Gemini). Auto-fires per Effort Calibration. |

### Your Phase-Based PM System
**Installed:** _change to Yes once configured_
**Strengths:** _e.g. spec-driven development, context rot prevention, autonomous execution_
**Best for:** _e.g. structured multi-phase builds, long sessions, full project lifecycle_

| Pattern | Use When |
|---------|----------|
| `<your command>` | _what it's good for_ |

### Your PR / Code Review System
**Installed:** _Yes / No_
**Strengths:** _PR pipelines, review cycles, code-focused workflows_
**Best for:** _feature implementation, code review, lint workflows_

| Pattern | Use When |
|---------|----------|
| `<your command>` | _what it's good for_ |

### Your Specialist Agents
**Installed:** _Yes / No_
**Strengths:** _domain expertise per agent_
**Best for:** _pair with orchestrators via combo syntax_
**Key agents:** _list 5–10 specialists you actually use_

### Your Knowledge / Search Layer
**Installed:** _Yes / No (Graphify, Context7, Exa, Firecrawl, etc.)_
**Strengths:** _live docs, web search, knowledge graph indexing_
**Best for:** _research, onboarding, cross-content reasoning_

### Direct Execution
**Strengths:** Zero overhead
**Best for:** Quick edits, lookups, single-file changes, casual questions, git operations

> **Add new sections with the same shape.** When you install a new workflow system, document it here so Cortex can route to it.

---

## Combo Syntax

Combine agents with workflow patterns:

```
Use the [Agent] agent. ralplan "task"          — Agency Agent + OMC
Use the [Agent] agent. /feature-dev "task"     — Agency Agent + ECC
Use the [Agent] agent. autopilot: task         — Agency Agent + OMC (lightweight)
```

Multi-agent parallel:

```
-- Run in parallel --
Use the [Agent A] agent. ralplan "sub-task 1"
Use the [Agent B] agent. ralplan "sub-task 2"
-- Then reconcile --
Use the [Agent C] agent. autopilot: "Reconcile outputs"
```

---

## Decision Shortcuts

> Starter set. Add your own as you discover them. `/cortex-learn` will surface candidates from your log automatically.

| Task Type | Default Route | Tier |
|-----------|---------------|------|
| Plan / architect / design system | OMC > /ccg pre-plan cross-check → ralplan > Software Architect | L3 |
| Build feature (backend) | OMC > ralplan > Backend Architect | L3 |
| Build feature (frontend) | OMC > ralplan > Frontend Developer | L3 |
| Build (well-scoped, brief locked, single specialist) | OMC > autopilot > [specialist] | L3 |
| Build (small bounded edits, ≤100 LOC, single domain) | Direct > batched-edits | L2 |
| Code review | ECC > code-review (or your equivalent) | L2 |
| Security audit | OMC > /ccg attack-surface pass → ralplan > Security Engineer | L4 |
| Research / analysis | OMC > deep-research (Exa + Firecrawl) | L2 |
| Quick bug fix | Direct execution | L1 |
| Trivial task (no overhead) | Direct execution | L1 |
| Requirements unclear | OMC > /ccg framing pass + clarifying interview | L3 |
| Must be perfect | OMC > /ccg pre-gate → ralph | L4 |
| Multi-domain build (≥2 disciplines) | OMC > /team > [Specialist A ∥ Specialist B ∥ …] → reconciler agent | L3 |
| Cross-cutting audit (security + perf + a11y) | OMC > /team > parallel domain auditors → /ccg reconciler | L3 |

---

## Adding New Workflows

When you say "add X to Cortex", add a new section to the registry with:
- Name and codename
- Installed status
- Strengths (1 line)
- Best for (1 line)
- Pattern table (name + when to use)
- Update the Decision Shortcuts table if any defaults change
