# Cortex — Workflow Routing Layer

> Meta-router that sits above all workflow systems. Loaded globally across all projects.
> When you install a new workflow system, add it here with `"add X to Cortex"`.

---

## Routing Protocol

**Default to routing.** Cortex should be engaged rather than bypassed. Run the full protocol for every non-trivial task, and when a task sits on the borderline between trivial and non-trivial, route it rather than skip it. The Skip protocol below is reserved for genuinely trivial work, not for anything you are unsure about.

Before starting any non-trivial task:

1. **Classify** — build / review / plan / research / debug / design / quick fix
2. **Calibrate** — pick effort tier (L1–L4) using heuristics in the Effort Calibration section. **Apply the anti-inflation rule first.**
3. **Hint** — run `python3 ~/.claude/bin/cortex hint "<task>" --class <c>`. Surfaces similar past routes weighted by outcome (shipped adds signal, corrected / abandoned subtract). **Advisory, not a decision** — factor it in, then still decide. Filter by class only while the log is small (under ~150 routes); adding `--tier` fragments the pool into buckets of 1–5 and returns nothing useful. Reintroduce `--tier <L>` once class-only pools regularly exceed ~15.
4. **Route** — pick the workflow system from the registry below
5. **Specialise** — pick the pattern + agent(s). **Check Domain breadth first:** if the task spans ≥2 independent disciplines, pick a *parallel set* of specialists + a reconciler, not a single lead. Single-agent is the exception for cross-domain work, not the default.
6. **State + Log** — one line: `[System] > [Pattern] > [Agent(s)] @ [Tier]` (fan-outs render as `[Agent A ∥ Agent B] → Reconciler`). Log via `cortex log-line` with three structured confidence flags — see **Three confidences** below. The CLI prints auto-trigger hints based on which one is low.
7. **Execute** — run the work. Listen for correction triggers: "reroute", "actually use X", "go back", "switch to X", "this didn't work", "wrong approach", "let me retry with X". Any of these fires `cortex reroute --to "new-route"` — no permission needed.
8. **Outcome** — when the task concludes, run `python3 ~/.claude/bin/cortex outcome <shipped|abandoned|partial|corrected> [--note "..."]`. Default to `shipped` if the work landed and the user didn't push back; `partial` if you stopped before the goal; `abandoned` if the route was wrong and you moved on without rerouting. Feeds hint quality for future routes.

**Skip protocol** — for quick lookups, file reads, casual questions, single-line edits: no hint, no calibration, no state line, no log, no outcome. Just do it.

### Three confidences (used at step 6)

Confidence isn't one number — three dimensions matter independently, each with its own auto-trigger:

| Dimension | Question being answered | If `low` → auto-trigger |
|-----------|-------------------------|--------------------------|
| **`--route-confidence`** | Am I picking the right system + pattern? | Rerun `cortex hint` with a broader `--min-similarity 0.05`, or fire the multi-model council to cross-check |
| **`--tier-confidence`** | Is this really L3, or could L2 have worked? | Flagged automatically for the next `cortex audit-tiers` review pass |
| **`--spec-confidence`** | Do I actually understand what the user wants? | **Stop before executing** — run a clarifying interview first. This is the strongest auto-trigger |

The legacy `--confidence` flag still works and seeds all three. Prefer the structured flags when one dimension is meaningfully different from the others — e.g. *high route, high tier, low spec* is the canonical "I know the right tool, I'm just not sure what they want."

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
| **L4** | Max | opus (max effort) | ultrathink | iterate-until-verified | full verify loop | parallel team / background fan-out |

### Anti-inflation rule (read this first)

**L3 must justify itself against L2, not the other way around.** Picking L3 because the work "feels important" or "is real" is inflation. To pick L3, you must be able to name a concrete failure mode that L2 would actually produce — e.g. "L2 would skip the verifier pass and this touches auth," or "L2 wouldn't fan out, but the work spans 3 domains."

Sanity check before locking L3 or L4 — answer "no" to all three means **L2**:

1. **Cost of being wrong** — if this ships broken, does it cost money, lose trust, or break prod?
2. **Genuine uncertainty** — is the solution actually unclear, or do I just need to type it out?
3. **Non-trivial verification** — does proving correctness need more than a single read-through?

The most common inflation pattern is reflexive bumping on "customer-facing" or "≥2 files touched". Resist.

### Calibration heuristics (pick the highest that applies — but apply the anti-inflation rule above first)

- **Blast radius** — reversible local edit → L1/L2; touches prod, migrations, shared infra, auth → L3/L4
- **Ambiguity** — clear one-liner → L1/L2; fuzzy spec where the wrong interpretation is plausible → L3 + clarifying interview first
- **Stakes** — throwaway / personal → L1/L2; **customer-facing alone is not L3** — customer-facing **and** irreversible (prod data, migrations, payments, auth) → L3; life-affecting / money-moving / security-critical → L4
- **Novelty** — familiar pattern → L2; new framework / unfamiliar SDK where the API shape is unknown → L3 + docs lookup
- **Reversibility** — can undo with one command → drop a tier; can't undo without manual recovery → bump a tier
- **User signal** — uncertain or exploratory tone → bump a tier; decisive and scoped → keep or drop
- **Domain breadth** — **single domain** → one specialist (default); **≥2 independent domains** (e.g., backend + frontend, infra + security, design + copy + a11y) → **fan out to parallel specialists + a reconciler**. Breadth picks the *shape* (multi-agent), not the *tier* — an L2 multi-agent run is fine when each leg is well-scoped. Bump to L3 only if the legs interact in non-obvious ways or the reconciliation itself is hard.

### Override phrases

| Phrase | Effect |
|--------|--------|
| `"go light"` / `"quick and dirty"` / `"cheap it"` | Force L1 |
| `"standard"` / `"normal"` | Force L2 |
| `"be thorough"` / `"do it properly"` | Force L3 |
| `"must be perfect"` / `"bulletproof"` / `"ultrathink"` | Force L4 |
| `"max effort"` / `"xhigh"` | Force L4 at maximum reasoning effort |
| `"bump it"` | Raise one tier |
| `"drop it"` | Lower one tier |

### Rules

- **L1 tasks skip the full routing protocol** — don't calibrate trivia, just do them
- **Tier is declared out loud before execution** — silent calibration breaks course-correction
- **One tier per task** — don't re-calibrate mid-flow unless something goes sideways (then stop, re-plan, re-state)
- **Tier and workflow are independent** — L4 on a phase-based build is that system's autonomous mode with full verify, not forced into a different orchestrator
- **Don't inflate** — L3 and L4 cost real tokens; the anti-inflation rule above is the primary defence, this is the reminder
- **Multi-agent is not inflation** — if *Domain breadth* fires (≥2 independent disciplines), parallel specialists is the *correct* shape, not an upgrade. Single-agent on a cross-domain task is a routing bug. Declare the fan-out in the routing line — at whatever tier the work actually warrants (L2 multi-agent is real): `OMC > /team > [Agent A ∥ Agent B] → Reconciler @ L2`
- **Shape and tier are orthogonal** — multi-agent fan-out is a *shape* decision (breadth heuristic), tier is a *depth* decision (everything else). Don't conflate.

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

### Build-checkpoint review (optional pattern)

CCG cross-checks **plans** before you build. The mirror pattern cross-checks **diffs** before they land: at a build checkpoint, hand the finished diff to a model from a *different* family than the one that wrote it, and have it report structured findings.

This is vendor-neutral by design — any second model family works (a different provider's CLI, a different model on the same provider, a local model). The value is the family boundary, not the specific vendor.

| Depth | Use When |
|-------|----------|
| **Single critic** (default) | L2/L3 builds with moderate risk — one cross-family reviewer on the finished diff, either spec-conformance mode or devil's-advocate mode |
| **Panel + judge** | Any high-risk trigger: auth / payments / migrations / data deletion, diff >300 LOC or >5 files, weak tests, architectural or API-contract change, external integrations, security exposure. Max 3 reviewers; one model acts as judge and synthesises a verdict with dissent noted |
| **Rival test generation** | Reviewer proves a flaw by writing a failing test — objective, no debate needed |
| **Skip** | Small local diffs, mechanical changes, well-tested code |

**Rules:**
- **Advisory by default** — a BLOCK verdict escalates to the human, it never auto-rejects.
- **One canonical review packet per checkpoint** — spec + plan + diff + tests + stated uncertainties. Reviewers see the same packet.
- **Findings must be concrete** — severity, `file:line`, evidence, and a reproducible failure scenario. No vague notes.
- **Verdicts are judged, never raw** — PASS / CAUTION / BLOCK with dissent noted, not three transcripts pasted together.
- **Effort tier rides the build task's tier** — single critic at L2/L3, panel when a risk trigger hits.

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

### Log write (part of routing protocol step 6)

After declaring the routing line, run this Bash call as an indivisible part of the State step.

**Form A — natural routing line (preferred):**

```bash
python3 ~/.claude/bin/cortex log-line \
  "<routing line, e.g. OMC > ralplan > Backend Architect @ L3>" \
  "<task description in 1 line>" \
  --class <build|review|plan|research|debug|design|quickfix> \
  --tier-reason "<heuristic that drove the tier>" \
  --system-reason "<why this system won over alternatives>" \
  --route-confidence <high|med|low> \
  --tier-confidence <high|med|low> \
  --spec-confidence <high|med|low>
```

The parser accepts the same `System > Pattern [> Agent] @ L<n>` shape Cortex declares, including bracketed tags.

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

### In-session visibility rule — "non-obvious tags"

For L2 routes matching default shortcuts, show the clean routing line only: `OMC > autopilot > Frontend Developer @ L2`.

For **non-obvious routes**, append 2–3 bracketed reasoning tags to the line itself so the reasoning is visible immediately:

- **Tier bumped above L2** (L3/L4) — show `[tier=<heuristic>]`
- **System chosen when another was close** — show `[system=<tiebreaker>]`
- **Specialist agent attached where a generic would've worked** — show `[agent=<reason>]`

Tags always live in the log (`tier_reason`, `system_reason`). The in-session display is just for immediate readability on surprising routes.

### Phase progression (data-triggered, not calendar-triggered)

- **Phase 1 — Visibility (active):** every route is logged. `/cortex-log` shows the last 20 with full reasoning.
- **Phase 2 — Pattern surfacing (activates at ~20 routes):** `/cortex-learn` detects `(class, system, pattern)` tuples that repeat ≥3 times and proposes them as Decision Shortcut candidates. The user approves, modifies, or dismisses — the tool does not auto-edit.
- **Phase 3 — Similarity bias (active, advisory):** before declaring a non-trivial routing line, run `cortex hint "<task>"` to surface similar past routes weighted by outcome (`shipped` adds signal, `corrected` / `abandoned` subtract). Output is **advisory only** — factor it in, still decide. Negative scores mean "past attempts at this route failed" — treat as anti-signal. Hint quality improves automatically as outcomes accumulate.
- **Phase 4 — Outcome + correction capture (active):** every routed task ends with an outcome — `shipped`, `abandoned`, `partial`, or `corrected` — captured with `cortex outcome <state>`. **Correction triggers** (any of these fires `cortex reroute`, no permission needed): `"reroute"`, `"actually use X"`, `"go back"`, `"switch to X"`, `"this didn't work"`, `"wrong approach"`, `"let me retry with X"`, `"that was wrong, try X"`. The last log entry is marked `outcome=corrected`, `user_correction` holds the new route, and the next logged route gets `redirect_from` linked. Over time this builds the labelled dataset Phase 3 learns from.

### Commands

| Command | Purpose |
|---------|---------|
| `/cortex-log` | Show last 20 routes with full reasoning. Pass `--project X` to filter |
| `/cortex-learn` | Detect repeating patterns, write proposals |
| `/cortex-learn --check` | Terse session-start check — silent if no pending pattern |
| `/cortex-reroute "new route"` | Mark last route as corrected |
| `cortex hint "<task>" [--class build]` | Surface similar past routes weighted by outcome. Class-only filtering while the log is small; add `--tier` back once pools regularly exceed ~15. Defaults: `--min-similarity 0.15 --top 5` |
| `cortex outcome <state> [--note "..."]` | Mark the last route's outcome — `shipped` / `abandoned` / `partial` / `corrected`. Fires at end of task automatically; can also be invoked explicitly |
| `cortex audit-tiers [--tier L3]` | List every L3/L4 (or filtered) route with task + reasoning + outcome — eyeball whether L2 would have sufficed. `--reclassify <task_hash> --to L2 --note "why"` reclassifies an entry, preserving the original |
| `cortex doctor` | Audit cortex setup for drift between docs, skills, and log |

### Session-start behavior

At the start of any session where a non-trivial task arrives, run `cortex learn --check` **before** the first routing decision. If it prints a pending pattern, mention it in one line and continue.

### Design principles

- **Visibility first, learning second.** The log is useful at T=0 (per-decision audit) and grows into a learning substrate.
- **Approve, don't auto-apply.** The learning layer proposes; you decide. No silent edits.
- **Data-triggered phases.** No calendar rituals, no monthly retros. Thresholds fire phases automatically.
- **Correction over prediction.** The highest-quality signal is the user saying "reroute" — explicit, unambiguous, ground truth.

---

## Workflow Registry

> **This is YOUR config.** The framework above is universal; the systems below are personal. Add the orchestrators, specialists, and tools you actually use.
>
> One example is filled in (OMC). The rest are stubs — replace with your stack. See `examples/cortex.md` for what a fully populated registry looks like.

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

### Your Build-Checkpoint Reviewer
**Installed:** _Yes / No_
**Strengths:** _cross-family review of diffs at checkpoints — structured findings, judged verdict_
**Best for:** _catching builder drift, logic bugs, and risky diffs before they land_
**Note:** _see "Build-checkpoint review" under Effort Calibration for the pattern. Any second model family works._

| Pattern | Use When |
|---------|----------|
| `<single critic>` | _default for moderate-risk L2/L3 diffs_ |
| `<panel + judge>` | _high-risk triggers: auth, payments, migrations, large diffs_ |

### Your Secret Scanner
**Installed:** _Yes / No_
**Strengths:** _deterministic secret detection (regex + entropy) — no model in the loop, reproducible pass/fail_
**Best for:** _pre-commit and CI gates; pairs with model-based security review for defense in depth_

| Pattern | Use When |
|---------|----------|
| `<scan staged changes>` | _pre-commit gate_ |
| `<scan git history>` | _auditing an existing repo_ |

### Your Specialist Agents
**Installed:** _Yes / No_
**Strengths:** _domain expertise per agent_
**Best for:** _pair with orchestrators via combo syntax_
**Key agents:** _list 5–10 specialists you actually use_

### Your Knowledge / Search Layer
**Installed:** _Yes / No (knowledge graph indexer, live-docs MCP, web search, page extraction, etc.)_
**Strengths:** _live docs, web search, knowledge graph indexing_
**Best for:** _research, onboarding, cross-content reasoning_

### Your Document / Deliverable Skills
**Installed:** _Yes / No (Word, Excel, PowerPoint, PDF, video, etc.)_
**Strengths:** _programmatic generation of real file-type deliverables_
**Best for:** _reports, models, decks, exports — auto-triggers on file type_

### Direct Execution
**Strengths:** Zero overhead
**Best for:** Quick edits, lookups, single-file changes, casual questions, git operations

> **Add new sections with the same shape.** When you install a new workflow system, document it here so Cortex can route to it.

---

## Combo Syntax

Combine agents with workflow patterns:

```
Use the [Agent] agent. ralplan "task"          — Specialist agent + OMC
Use the [Agent] agent. /feature-dev "task"     — Specialist agent + your PR system
Use the [Agent] agent. autopilot: task         — Specialist agent + OMC (lightweight)
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
| Build checkpoint review (pre-commit / risky diff) | Build-checkpoint reviewer > single critic, or panel + judge on a risk trigger | L2–L3 |
| Code review | Your PR / code review system | L2 |
| Hardcoded secret scan (pre-commit / CI gate) | Direct > secret scanner (deterministic) — pair with Security Engineer for deep review | L1 |
| Security audit | OMC > /ccg attack-surface pass → ralplan > Security Engineer | L4 |
| Research / analysis | OMC > deep-research (web search + page extraction) | L2 |
| Library / framework docs | Live-docs MCP (direct) | L1 |
| Word / PDF / PPT / Excel deliverable | Document skill — auto-triggers on file type | L1 |
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
