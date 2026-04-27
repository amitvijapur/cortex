# Cortex — Example Populated Config

> This is an example of a fully-populated `cortex.md` from a real Claude Code user. Routes have been generalized — your stack will look different.
>
> Use this as a *shape reference*, not a copy-paste target. The framework (Routing Protocol, Effort Calibration, Self-Learning Loop) is identical to `templates/cortex.md`. The Workflow Registry and Decision Shortcuts below show what it looks like when you populate it with a real, opinionated stack.

---

## Workflow Registry — populated example

### OMC (oh-my-claudecode)
**Installed:** Yes
**Strengths:** Multi-agent orchestration, verify/fix loops, parallel execution, team mode
**Best for:** Complex builds, planning, multi-step tasks needing quality gates, research

| Pattern | Use When |
|---------|----------|
| `ralplan "task"` | Important work needing planning + verify/fix loops. **Default for non-trivial work.** |
| `autopilot: task` | Well-defined, lower-risk tasks. One-shot autonomous. |
| `ralph: task` | Must be bulletproof. Won't stop until verified complete. |
| `/team N:executor "task"` | Parallel execution, multiple perspectives. |
| `/deep-interview` | Requirements unclear. Clarify before building. |
| `ultrawork` | High-throughput parallel task completion. |
| `/ccg` | Tri-model orchestration (Claude + Codex + Gemini). |
| `/oh-my-claudecode:external-context` | Web research and documentation lookup. |
| `/oh-my-claudecode:self-improve` | Autonomous code improvement with benchmarking loops. |
| `/oh-my-claudecode:verify` | Turn "it works" into concrete evidence. |
| `/oh-my-claudecode:deep-dive` | 2-stage: trace root cause then define requirements. |

### GSD (Get Shit Done)
**Installed:** Yes
**Strengths:** Context rot prevention, spec-driven development, phase-based project management
**Best for:** Structured multi-phase builds, long sessions, preventing quality degradation

| Pattern | Use When |
|---------|----------|
| `/gsd-new-project` | Initialise a new project with spec-driven planning. |
| `/gsd-plan-phase` | Create detailed phase plan with verification. |
| `/gsd-execute-phase` | Execute all plans in a phase with wave-based parallelisation. |
| `/gsd-autonomous` | Run all remaining phases autonomously. |
| `/gsd-do "task"` | Route freeform text to the right GSD command. |
| `/gsd-discuss-phase` | Gather context through adaptive questioning before planning. |
| `/gsd-debug` | Systematic debugging with persistent state across context resets. |
| `/gsd-resume-work` | Resume from previous session with full context restoration. |

### ECC (claude-plugins-official)
**Installed:** Yes
**Strengths:** Code-focused workflows, PR pipelines, review cycles, LSP integration
**Best for:** Feature implementation, code review, PR workflows

| Pattern | Use When |
|---------|----------|
| `feature-dev` | End-to-end feature implementation with structure. |
| `code-review` | Review code for quality, bugs, security. |
| `pr-review-toolkit` | PR-specific review with checklist. |
| `ralph-loop` | Persistent loop until task passes. |
| `code-simplifier` | Reduce complexity, clean up code. |

### Adversarial Spec
**Installed:** Yes
**Strengths:** Multi-model debate for spec hardening, cross-LLM adversarial review
**Best for:** Hardening specs, API contracts, schemas, security designs before implementation
**Requires:** At least one external API key

| Pattern | Use When |
|---------|----------|
| `/adversarial-spec "spec"` | Harden a spec/contract through multi-model adversarial debate. |

### Agency Agents (~/.claude/agents/)
**Installed:** Yes
**Strengths:** Deep domain expertise per agent
**Best for:** Pair with orchestrators via combo syntax

Key agents:

| Domain | Agent(s) |
|--------|----------|
| Backend / API | Software Architect, Backend Architect |
| Frontend / UI | UI Designer, Frontend Developer |
| Database | Database Optimiser |
| Security | Security Engineer |
| AI / ML | AI Engineer, Voice AI Integration Engineer |
| DevOps | DevOps Automator |
| UX | UX Researcher |
| Brand / copy | Brand Guardian, Content Creator |
| Growth | Growth Hacker, Agentic Search Optimizer |
| Onboarding | Codebase Onboarding Engineer, Minimal Change Engineer |
| Cross-functional | Chief of Staff |

### Tessl Skills
**Installed:** Yes
**Strengths:** Framework-specific expertise with live docs
**Best for:** React, Next.js, Stripe, Python tooling, frontend design

| Skill | Use When |
|-------|----------|
| `tessl__senior-frontend` | React, Next.js, TypeScript, Tailwind work |
| `tessl__nextjs-developer` | Next.js 14+ App Router, server components |
| `tessl__stripe-integration` | Payment processing, subscriptions |
| `tessl__modern-python` | Python project setup with uv, ruff |
| `tessl__frontend-design` | High-quality UI implementation |

### Domain Models (Specialized)
**Installed:** Yes (Kronos, etc.)
**Strengths:** Pre-trained foundation models for specific domains where generic LLMs underperform
**Best for:** Zero-shot baselines, feature generation, fine-tuning on proprietary data

#### Kronos — Financial Candlestick Forecasting
**Source:** [github.com/shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)
**What it does:** Open-source foundation model for OHLCV K-line prediction. Trained on 45+ exchanges.

| Pattern | Use When |
|---------|----------|
| `kronos predict <ticker>` | Zero-shot OHLCV forecast |
| `kronos backtest <ticker>` | Evaluate predictions vs historical |
| `kronos finetune <dataset.csv>` | Adapt to proprietary universe |

### Graphify (Knowledge Layer)
**Installed:** Yes
**Source:** [github.com/safishamsi/graphify](https://github.com/safishamsi/graphify)
**Strengths:** Turns mixed content (code, docs, papers, images, videos) into a queryable knowledge graph
**Best for:** Research-heavy projects, cross-content reasoning, onboarding doc-heavy codebases

| Pattern | Use When |
|---------|----------|
| `/graphify .` | Build a knowledge graph for the current folder |
| `/graphify ./path --update` | Merge new content into an existing graph |
| `/graphify ./path --watch` | Auto-sync as files change |
| `/graphify query "..."` | Semantic question across all indexed content |
| `/graphify path "NodeA" "NodeB"` | Find shortest conceptual path between two nodes |

### MCP Capabilities
**Installed:** Yes
**Strengths:** Live docs, AI web search, page extraction, faster edits
**Best for:** Powering research, documentation lookup

| MCP | What It Does | Auto-Used By |
|-----|-------------|--------------|
| Context7 | Live docs for 10k+ packages | `documentation-lookup` skill |
| Exa | AI-native web search | `deep-research`, `external-context` skills |
| Firecrawl | Full page extraction to markdown | `deep-research` |
| Supabase | DB queries, auth, storage | Database Optimiser agent |
| Slack | Send/read messages | Team communication |

### Cloud MCPs (claude.ai connected)
**Installed:** Yes
**Strengths:** Direct access to productivity tools, communication, design

| MCP | Use When |
|-----|----------|
| Figma | Design-to-code, inspecting mockups |
| Notion | Knowledge base, docs, project wikis |
| Gmail | Email context, drafting replies |
| Google Calendar | Scheduling, availability checks |
| Granola | Meeting transcripts and notes |
| Canva | Visual assets, presentations |

### Direct Execution
**Strengths:** Zero overhead
**Best for:** Quick edits, lookups, single-file changes, casual questions, git operations

---

## Decision Shortcuts — populated example

| Task Type | Default Route | Tier |
|-----------|---------------|------|
| Plan / architect | OMC > /ccg → ralplan > Software Architect | L3 |
| Build feature (backend) | OMC > ralplan > Backend Architect | L3 |
| Build feature (frontend) | OMC > ralplan > Frontend Developer + tessl | L3 |
| Build (well-scoped, brief locked, single specialist) ✓ | OMC > autopilot > [specialist] | L3 |
| Build (small bounded edits, ≤100 LOC, single domain) ✓ | Direct > batched-edits | L2 |
| Multi-phase project build | GSD > /gsd-new-project then /gsd-autonomous | L3 |
| Long session / context-heavy | GSD > /gsd-do (context rot prevention) | L2 |
| Code review | ECC > code-review | L2 |
| Security audit | OMC > /ccg attack-surface pass → ralplan > Security Engineer | L4 |
| Harden spec / API contract | Adversarial Spec > /adversarial-spec | L4 |
| Library / framework docs | Context7 (direct) or tessl query_library_docs | L1 |
| Research / analysis | OMC > deep-research (Exa + Firecrawl) | L2 |
| Build UI with design system | Copy DESIGN.md + frontend-design skill | L3 |
| Design-to-code | Figma MCP > get_design_context + Frontend Developer | L3 |
| Quick bug fix | Direct execution | L1 |
| Trivial task | Direct execution | L1 |
| Database work | Supabase MCP + Database Optimiser agent | L2 |
| Visual QA | Chrome DevTools MCP | L2 |
| Requirements unclear | OMC > /ccg framing pass + /deep-interview | L3 |
| Must be perfect | OMC > /ccg pre-gate → ralph | L4 |
| Debug (persistent across resets) | GSD > /gsd-debug | L3 |
| Research cross-content (code + papers + media) | Graphify index + OMC deep-research | L3 |
| Onboard onto doc-heavy codebase | Graphify + /gsd-map-codebase + Codebase Onboarding | L3 |
| Small surgical fix | OMC > autopilot > Minimal Change Engineer | L1 |
| Cross-functional ops | OMC > autopilot > Chief of Staff | L2 |
| Financial OHLCV forecast | Kronos > predict | L2 |
| **Multi-domain build (≥2 disciplines)** | **OMC > /team > [Specialist A ∥ Specialist B ∥ …] → reconciler** | **L3** |
| Cross-cutting audit (security + perf + a11y) | OMC > /team > parallel domain auditors → /ccg reconciler | L3 |
| Full-stack feature (API + UI + data) | OMC > /team > [Backend Architect ∥ Frontend Developer ∥ Database Optimiser] → /ccg reconciler | L3 |

---

## Notes on building your own

The patterns that have proven valuable across many projects:

- **CCG auto-firing on irreversible actions** — single biggest catch for "wait, are you sure" moments
- **Domain breadth → multi-agent fan-out by default** — prevents single-specialist tunnel vision
- **`Direct > batched-edits @ L2` for tightly-scoped multi-file work** — when OMC routing overhead exceeds the actual work
- **Self-learning log** — at ~30 routes, two patterns auto-surfaced that I'd been doing instinctively but never codified

Your patterns will be different. The framework is universal; the routes are personal.
