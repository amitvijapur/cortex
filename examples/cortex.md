# Cortex — Example Populated Config

> This is an example of a fully-populated `cortex.md` from a real Claude Code user. Routes have been generalized — your stack will look different.
>
> Use this as a *shape reference*, not a copy-paste target. The framework (Routing Protocol, Effort Calibration, Self-Learning Loop) is identical to `templates/cortex.md`. The Workflow Registry and Decision Shortcuts below show what it looks like when you populate it with a real, opinionated stack.
>
> Convention used below: locally-cloned tools live at `~/tools/<name>/` with a thin CLI wrapper at `~/.claude/bin/<name>`.

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
| `/ccg` | Tri-model orchestration (Claude + Codex + Gemini). Auto-fires per Effort Calibration. |
| `/oh-my-claudecode:external-context` | Web research and documentation lookup. |
| `/oh-my-claudecode:self-improve` | Autonomous code improvement with benchmarking loops. |
| `/oh-my-claudecode:verify` | Turn "it works" into concrete evidence. |
| `/oh-my-claudecode:deep-dive` | 2-stage: trace root cause then define requirements. |

### GSD (Get Shit Done)
**Installed:** Yes
**Strengths:** Context rot prevention, spec-driven development, phase-based project management, autonomous execution
**Best for:** Structured multi-phase builds, long sessions, preventing quality degradation, full project lifecycle

| Pattern | Use When |
|---------|----------|
| `/gsd-new-project` | Initialise a new project with spec-driven planning. |
| `/gsd-plan-phase` | Create detailed phase plan with verification. |
| `/gsd-execute-phase` | Execute all plans in a phase with wave-based parallelisation. |
| `/gsd-autonomous` | Run all remaining phases autonomously (discuss → plan → execute per phase). |
| `/gsd-do "task"` | Route freeform text to the right GSD command. |
| `/gsd-discuss-phase` | Gather context through adaptive questioning before planning. |
| `/gsd-debug` | Systematic debugging with persistent state across context resets. |
| `/gsd-map-codebase` | Scan and index codebase structure for context. |
| `/gsd-code-review` | Review changed files for bugs, security, quality. |
| `/gsd-ship` | Create PR, run review, prepare for merge. |
| `/gsd-resume-work` | Resume from previous session with full context restoration. |
| `/gsd-fast` | Execute trivial task inline — no subagents, no planning overhead. |

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
| `commit-commands` | Structured git commits. |
| `security-guidance` | Continuous 3-layer security review as code is written (per-edit pattern check → per-turn model review → agentic review on commit/push). |

### Adversarial Spec
**Installed:** Yes
**Strengths:** Multi-model debate for spec hardening, cross-LLM adversarial review
**Best for:** Hardening specs, API contracts, schemas, security designs before implementation
**Requires:** At least one external model API key

| Pattern | Use When |
|---------|----------|
| `/adversarial-spec "spec"` | Harden a spec/contract through multi-model adversarial debate. |

### Sentinel (Multi-Model Build Review)
**Installed:** Yes — protocol skill + cross-family reviewer CLIs
**Strengths:** Cross-family review of build-phase diffs at checkpoints — structured findings, judge synthesis with dissent noted, spec-conformance checking
**Best for:** Catching builder drift, logic bugs, and risky diffs before they land. The BUILD-phase counterpart to CCG's plan validation.

| Pattern | Use When |
|---------|----------|
| Medium — single critic | Default for L2/L3 builds with moderate risk: one cross-family reviewer on the finished diff (spec-check or devil's-advocate mode) |
| High — panel + judge | Any high-risk trigger: auth / payments / migrations / data deletion / agent routing, diff >300 LOC or >5 files, weak tests, architectural or API-contract change, external integrations, security exposure |
| Rival test generation | Reviewer proves a flaw with a failing test — objective, no debate needed |
| Skip | Small local diffs, mechanical changes, well-tested code |

**Rules:** advisory by default — BLOCK escalates to a human, never auto-rejects; one canonical review packet per checkpoint (spec + plan + diff + tests + uncertainties); findings carry severity, `file:line`, evidence, and a concrete failure scenario; max 3 reviewers, one is the default; verdicts are judged (PASS / CAUTION / BLOCK with dissent), never raw transcripts.

**How it fits:** CCG cross-checks *plans* before building; Sentinel cross-checks *diffs* before they land.

### Gitleaks (Secret Scanning CLI)
**Installed:** Yes (`brew install gitleaks`)
**Source:** [github.com/gitleaks/gitleaks](https://github.com/gitleaks/gitleaks)
**Strengths:** Fast, deterministic secret scanner (regex + entropy) for git history, working tree, and staged changes. No model in the loop — reproducible pass/fail.
**Best for:** Catching hardcoded secrets (API keys, tokens, private keys) before they land in a commit or PR.

| Pattern | Use When |
|---------|----------|
| `gitleaks git -v` | Scan the full git history of a repo for leaked secrets. |
| `gitleaks dir -v` | Scan a directory / working tree (files on disk, not git history). |
| `gitleaks protect --staged` | Scan staged changes before commit — the pre-commit gate. |
| pre-commit hook / CI action | Wire into `pre-commit` or GitHub Actions so every commit and PR is scanned. |

**How it fits:** the deterministic first line — cheap, reproducible, never hallucinates. Pair with a Security Engineer agent and continuous model-based review for defense in depth.

### Knowledge Work Plugins (Anthropic, first-party)
**Installed:** Yes — `data`, `legal`, `enterprise-search` enabled
**Strengths:** First-party plugins for non-code knowledge work
**Best for:** SQL / dashboards, contract triage, cross-tool search

| Plugin | Use When |
|--------|----------|
| `data` | SQL + dashboards + self-validation over a dataset — pairs with DuckDB / Supabase MCPs |
| `legal` | Contract / NDA triage and review |
| `enterprise-search` | Cross-tool search over email / chat / docs |
| `product-management` | PRDs, roadmaps, prioritisation (install on demand) |
| `bio-research` | PubMed / genomics / BioRender (install on demand) |

### Claude Tag Plugins (SaaS Connectors)
**Installed:** Pending — `claude plugin marketplace add anthropics/claude-tag-plugins`, then install services on demand
**Strengths:** 18 first-party SaaS connector plugins, one per service; credentials injected by the runtime, not embedded
**Best for:** Giving the agent direct, routable access to issue trackers, CRM, data warehouses, and observability

| Plugin | Use When |
|--------|----------|
| `jira` / `linear` / `asana` | Issue and project tracking |
| `salesforce` / `hubspot` | CRM — accounts, contacts, deals, pipeline |
| `datadog` / `grafana` / `pagerduty` / `sentry` | Observability and incident (pairs with SRE / Incident Responder agents) |
| `bigquery` / `snowflake` / `redshift` | Cloud data warehouse SQL (pairs with the `data` plugin) |
| `confluence` / `notion` / `google-drive` | Docs and knowledge base (dedupe against Cloud MCPs) |

**Effort tier default:** L1 to install or query; the task using it sets the real tier.

### Anthropic Official Skills
**Installed:** Yes
**Strengths:** First-party document creation / editing skills
**Best for:** Programmatic Word reports, Excel models, PowerPoint decks, PDF manipulation; canonical playbooks for shipping MCPs and skills

| Skill | Use When |
|-------|----------|
| `docx` | Create / read / edit Word documents — reports, memos, letters, templates |
| `pdf` | Read / extract / merge / split / fill / encrypt PDFs, OCR scanned PDFs |
| `pptx` | Create / read / edit slide decks — pitch decks, presentations, speaker notes |
| `xlsx` | Create / read / edit spreadsheets — formulas, charts, clean messy tabular data |
| `mcp-builder` | Canonical playbook when shipping an MCP server |
| `skill-creator` | Build / edit / benchmark Claude skills with eval support |

**Chains naturally:** backtest output → `xlsx` model → `pptx` deck → `pdf` export.

### Anthropic Financial Services Plugins
**Installed:** Yes
**Strengths:** First-party finance skills with Excel / PowerPoint integration
**Best for:** Financial modelling, equity research, earnings analysis, pitch decks, meeting prep

| Plugin | Use When |
|--------|----------|
| `financial-analysis` | DCF, comps, LBO, 3-statement models, competitive analysis, deck QC |
| `model-builder` | Build live Excel models — DCF, LBO, 3-statement, comps |
| `pitch-agent` | Comps + precedents + LBO → branded pitch deck, end to end |
| `market-researcher` | Sector / theme → industry overview, competitive landscape, peer comps |
| `earnings-reviewer` | Earnings call + filings → model update → note draft |
| `meeting-prep-agent` | Briefing pack before client meetings |
| `equity-research` | Earnings analysis, initiating coverage reports (install if doing equity research) |

### Community Skill Packs & Memory
**Installed:** Yes

| Tool | Use When |
|------|----------|
| `obsidian-skills` | Vault operations — Markdown / Bases / JSON Canvas via the Obsidian CLI. Powers "document builds in a notes vault as you go" |
| `claude-mem` | Automatic cross-session memory: captures sessions, compresses, injects relevant context |
| `last30days` | "What's new in the last 30 days" across Reddit / X / YouTube / HN — recency complement to deep-research |
| `defending-code harness` | Security work: `/threat-model`, `/vuln-scan`, `/triage`, `/patch` (Anthropic official; sandboxed pipeline needs Docker/gVisor) |

### Agency Agents (`~/.claude/agents/`)
**Installed:** Yes (280+ specialists across 20+ divisions)
**Strengths:** Deep domain expertise per agent
**Best for:** Pair with orchestrators via combo syntax. Run `/agents` to list.

| Domain | Agent(s) |
|--------|----------|
| Backend / API / architecture | Software Architect, Backend Architect |
| Frontend / UI | UI Designer, Frontend Developer |
| Database | Database Optimiser |
| Security | Security Engineer |
| AI / ML | AI Engineer, Voice AI Integration Engineer |
| DevOps | DevOps Automator |
| UX | UX Researcher |
| Brand / copy / content | Brand Guardian, Content Creator |
| Growth | Growth Hacker, Agentic Search Optimizer (AEO/GEO) |
| Finance | Finance Tracker, Investment Researcher, Tax Strategist, FP&A Analyst |
| Onboarding / minimal change | Codebase Onboarding Engineer, Minimal Change Engineer |
| Legal | Legal Client Intake, Legal Document Review, Legal Billing |
| HR / recruitment | HR Onboarding, Recruitment Specialist |
| Cross-functional | Chief of Staff |
| Localisation | Language Translator |

### Tessl Skills
**Installed:** Yes
**Strengths:** Framework-specific expertise with live docs
**Best for:** React, Next.js, Three.js, Stripe, Python tooling, frontend design

| Skill | Use When |
|-------|----------|
| `tessl__senior-frontend` | React, Next.js, TypeScript, Tailwind work |
| `tessl__nextjs-developer` | Next.js 14+ App Router, server components |
| `tessl__stripe-integration` | Payment processing, subscriptions |
| `tessl__modern-python` | Python project setup with uv, ruff, ty |
| `tessl__frontend-design` | High-quality UI implementation |
| `tessl__3d-web-experience` | Three.js, WebGL, interactive 3D |

### Hyperframes (HTML → MP4 video)
**Installed:** Yes — cloned at `~/tools/hyperframes/`
**Source:** [github.com/heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)
**Strengths:** Write HTML → render MP4. GSAP timelines, Tailwind browser runtime, Three.js / Lottie / Anime.js adapters
**Best for:** Product intros, social ads, animated explainers, motion graphics from CSV / PDF / URL / repo, captions synced to TTS

| Skill | Use When |
|-------|----------|
| `hyperframes` | Author video compositions — scenes, animations, captions, transitions |
| `hyperframes-cli` | Dev loop — `init`, `lint`, `inspect`, `preview`, `render`, `doctor` |
| `hyperframes-media` | TTS narration, transcription, background removal |
| `website-to-hyperframes` | URL → video. Product tour / social ad / promo from a link |

**Chains naturally:** landing page → `website-to-hyperframes` → 30s promo. Backtest results → `hyperframes` chart-race video.

### Graphify (Knowledge Layer)
**Installed:** Yes
**Source:** [github.com/safishamsi/graphify](https://github.com/safishamsi/graphify)
**Strengths:** Turns mixed content (code, docs, papers, images, videos) into a queryable knowledge graph
**Best for:** Research-heavy projects, cross-content reasoning, onboarding doc-heavy codebases

| Pattern | Use When |
|---------|----------|
| `/graphify .` | Build a knowledge graph for the current folder |
| `/graphify ./path --update` | Merge new content into an existing graph |
| `/graphify ./path --watch` | Auto-sync as files change — long-running work |
| `/graphify query "..."` | Semantic question across all indexed content |
| `/graphify path "NodeA" "NodeB"` | Find shortest conceptual path between two nodes |
| `/graphify explain "Concept"` | Surface god-nodes and surprising connections |

**Rituals:** onboarding (`/graphify .` + `/gsd-map-codebase`), pre-refactor dependency check ("what depends on X beyond direct imports?"), long-running project sync (`--watch`), local-vs-external research ("what's our prior work on X?" then deep-research). **Skip** on repos under ~20 files, single-file fixes, and throwaway scripts.

### Understand Anything (Codebase Knowledge Graph)
**Installed:** Trial — head-to-head vs Graphify not yet settled
**Source:** [github.com/Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)
**Strengths:** Code-only knowledge graph with guided architecture tours, layer visualisation (API / Service / Data / UI / Utility), and business-domain mapping. Tree-sitter for deterministic structure + a five-agent LLM pipeline for semantics.
**Best for:** Onboarding onto a single, code-only repo where guided tours beat a concept graph

| Pattern | Use When |
|---------|----------|
| `/understand` | Scan the repo and build the graph (incremental updates supported) |
| `/understand-dashboard` | Interactive web dashboard to explore the graph visually |
| `/understand-chat` | Ask natural-language questions about the codebase |
| `/understand-domain` | Extract business domains, flows, process steps |
| `/understand-onboard` | Generate an onboarding guide / guided tour |
| `/understand-diff` | Blast-radius analysis of current changes — pre-refactor impact check |

**vs Graphify:** Graphify spans code **+ docs + papers + media**; Understand Anything is code-only but goes deeper on code (tours, layers, domains). Mixed-content repos → Graphify. Pure-code repos → trial Understand Anything.

### Domain Models (Specialized)
**Installed:** Yes (Kronos, QuantMind)
**Strengths:** Pre-trained foundation models and extraction frameworks for domains where generic LLMs underperform
**Best for:** Zero-shot baselines, feature generation, fine-tuning on proprietary data
**Convention:** each lives at `~/tools/<name>/` with a wrapper at `~/.claude/bin/<name>`

#### Kronos — Financial Candlestick Forecasting
**Source:** [github.com/shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)
**What it does:** Open-source foundation model for OHLCV candlestick prediction. Trained on 45+ exchanges. Variants: mini → small (default) → base → large.

| Pattern | Use When |
|---------|----------|
| `kronos predict <ticker> [--lookback N --horizon N]` | Zero-shot OHLCV forecast |
| `kronos backtest <ticker> --strategy <name>` | Evaluate predictions vs historical |
| `kronos finetune <dataset.csv>` | Adapt to a proprietary universe / alt data |

**Don't use for:** single-asset alpha generation (use as a feature, not an oracle), regime shifts outside the training distribution, news/event-driven trading (price-only, no text awareness).

#### QuantMind — Financial Research Knowledge Extraction
**Source:** [github.com/LLMQuant/quant-mind](https://github.com/LLMQuant/quant-mind)
**What it does:** Ingests financial research at scale — arXiv papers, SEC filings, news — and turns it into a structured, queryable knowledge base via an LLM extraction pipeline.
**Status:** Trial — confirm output quality and per-paper cost before committing further.

| Pattern | Use When |
|---------|----------|
| `paper_flow(<source>)` | Extract structured knowledge from a single paper / filing / news item |
| `batch_run(<sources>)` | Ingest a batch of sources into the knowledge base |

**Don't use for:** graphing content you already own (use Graphify), financial modelling on extracted data (use the finance plugins), open-ended web research with citations (use deep-research).

### Design Systems Library
**Installed:** Yes — `~/design-systems/`
**Source:** [github.com/VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
**Strengths:** 58+ real-world `DESIGN.md` specs (Stripe, Linear, Vercel, etc.) as plain markdown
**Best for:** Giving a frontend build a real design language instead of generic AI aesthetics

| Pattern | Use When |
|---------|----------|
| Copy `DESIGN.md` into project root | Starting a new UI build — agents auto-detect it |
| Browse the library | Picking a design system to base the project on |

**Design pipeline:** `DESIGN.md` (tokens) → Figma MCP (`get_design_context`) → `frontend-design` / `tessl__senior-frontend` skill or Frontend Developer agent → `animate` → `polish` / `normalize` → `critique` / `audit` → Chrome DevTools MCP for visual QA.

### MCP Capabilities
**Installed:** Yes (infrastructure layer — consumed by the systems above)
**Strengths:** Live docs, AI web search, page extraction, faster edits, data access
**Best for:** Powering research, documentation lookup, and edit performance

| MCP | What It Does | Auto-Used By |
|-----|-------------|--------------|
| Context7 | Live docs for 10k+ packages | `documentation-lookup` skill, tessl `query_library_docs` |
| Exa | AI-native web search | `deep-research`, `external-context` skills |
| Firecrawl | Full page extraction to markdown | `deep-research` (Exa finds → Firecrawl extracts) |
| Scrapling | Adaptive scraper with anti-bot bypass (Cloudflare, DataDome) | Fallback when Firecrawl fails on bot-walled pages |
| Morph | Faster edits + semantic code search | Executor agents, edit operations |
| Supabase | DB queries, auth, storage, schema management | Database Optimiser agent, direct SQL |
| DuckDB | In-process OLAP — SQL over local Parquet / CSV / JSON | Backtest output analysis, ad-hoc tabular exploration |
| cortex-queue | Human-in-the-loop decision queue — `enqueue_decision()` / `await_decision()` / `ask_human()` | Long-running unsupervised loops that hit ambiguity |
| Slack | Send/read messages, manage channels | Team communication, notifications |

### Toolport (Local MCP Gateway)
**Installed:** Pending — `brew install --cask tsouth89/toolport/toolport` (or the install script)
**Strengths:** Local-first MCP gateway with lazy tool discovery — advertises four compact meta-tools instead of every server's full catalog
**Best for:** Cutting the per-session token cost of a large MCP surface; one shared server config across clients

| Pattern | Use When |
|---------|----------|
| Route MCP servers through the gateway | Many servers are registered and full catalogs bloat context every request |
| `toolport_search_tools "<query>"` | The agent should discover the right tool on demand rather than loading all upfront |

**Effort tier default:** L1 to install / query; L2 to re-wire the session's MCP config through it.

### Cloud MCPs (claude.ai connected)
**Installed:** Yes
**Strengths:** Direct access to productivity tools, communication, design, knowledge

| MCP | Use When |
|-----|----------|
| Figma | Design-to-code, inspecting mockups, Code Connect |
| Notion | Knowledge base, docs, project wikis |
| Gmail | Email context, drafting replies |
| Google Calendar | Scheduling, availability checks |
| Canva | Visual assets, presentations, social graphics |
| Granola | Meeting transcripts and notes |
| Scholar Gateway | Academic research, citations |
| GitHub | Issue triage, PR workflows |

### Chrome DevTools MCP
**Installed:** Yes
**Strengths:** Browser debugging, performance auditing, accessibility testing
**Best for:** Visual QA, Lighthouse audits, network debugging, a11y checks

### Direct Execution
**Strengths:** Zero overhead
**Best for:** Quick edits, lookups, single-file changes, casual questions, git operations

---

## Decision Shortcuts — populated example

| Task Type | Default Route | Tier |
|-----------|---------------|------|
| Plan / architect | OMC > /ccg pre-plan cross-check → ralplan > Software Architect | L3 |
| Build feature (backend) | OMC > ralplan > Backend Architect | L3 |
| Build feature (frontend) | OMC > ralplan > Frontend Developer + tessl | L3 |
| Build (well-scoped, brief locked, single specialist) ✓ | OMC > autopilot > [specialist] | L3 |
| Build (small bounded edits, ≤100 LOC, single domain) ✓ | Direct > batched-edits | L2 |
| Build checkpoint review (pre-commit / risky diff) | Sentinel > single critic (Medium), or panel + judge (High) | L2–L3 |
| Multi-phase project build | GSD > /gsd-new-project then /gsd-autonomous | L3 |
| Long session / context-heavy | GSD > /gsd-do (context rot prevention) | L2 |
| Resume previous work | GSD > /gsd-resume-work | L2 |
| Code review | ECC > code-review | L2 |
| PR workflow | ECC > pr-review-toolkit | L2 |
| Hardcoded secret scan (pre-commit / CI gate) | Direct > gitleaks (deterministic) — pair with Security Engineer for deep review | L1 |
| Security audit | OMC > /ccg attack-surface pass → ralplan > Security Engineer + defending-code harness | L4 |
| Harden spec / API contract | Adversarial Spec > /adversarial-spec | L4 |
| Library / framework docs | Context7 (direct) or tessl `query_library_docs` | L1 |
| Research / analysis | OMC > deep-research (Exa + Firecrawl) | L2 |
| Recency research (last-30-days, social) | last30days plugin | L1 |
| Vault note ops / build docs as you go | obsidian-skills plugin | L1 |
| Scrape a bot-walled page | Scrapling MCP (Firecrawl fallback) | L1 |
| Query parquet / CSV / JSON columnar | DuckDB MCP | L1 |
| Build UI with design system | Copy DESIGN.md from the design-systems library + `frontend-design` skill | L3 |
| Design-to-code | Figma MCP > `get_design_context` + Frontend Developer | L3 |
| Word / PDF / PPT / Excel deliverable | Anthropic skill (`docx` / `pdf` / `pptx` / `xlsx`) — auto-triggers on file type | L1 |
| Build an MCP server | `mcp-builder` skill + OMC > ralplan > Backend Architect | L3 |
| Build / edit / benchmark a Claude skill | `skill-creator` skill | L2 |
| Financial model — DCF / LBO / comps / 3-statement | `model-builder` or `financial-analysis` + `xlsx` skill | L3 |
| Pitch deck end-to-end | `pitch-agent` + `pptx` skill | L3 |
| Earnings analysis / model update | `earnings-reviewer` + `xlsx` / `docx` | L2 |
| Sector research → peer comps | `market-researcher` (or deep-research for broader scope) | L2 |
| SQL / dashboards over a dataset | Knowledge Work > `data` plugin + DuckDB / Supabase | L2 |
| Contract / NDA triage | Knowledge Work > `legal` plugin | L2 |
| Cross-tool search (email / chat / docs) | Knowledge Work > `enterprise-search` plugin | L1 |
| Video from a URL (product tour, promo, social ad) | Hyperframes > `website-to-hyperframes` | L2 |
| Motion-graphics video (explainer, chart race, captions+TTS) | Hyperframes > `hyperframes` + `hyperframes-media` | L2 |
| Quick bug fix | Direct execution | L1 |
| Trivial task (no overhead) | GSD > /gsd-fast or Direct execution | L1 |
| Small surgical fix / "touch as little as possible" | OMC > autopilot > Minimal Change Engineer | L1 |
| Database work | Supabase MCP + Database Optimiser agent | L2 |
| Visual QA | Chrome DevTools MCP | L2 |
| Requirements unclear | OMC > /ccg framing pass in parallel with /deep-interview | L3 |
| Must be perfect | OMC > /ccg pre-gate → ralph | L4 |
| Debug (persistent across resets) | GSD > /gsd-debug | L3 |
| Root cause investigation | OMC > /oh-my-claudecode:deep-dive | L3 |
| Prove it works (evidence) | OMC > /oh-my-claudecode:verify | L2 |
| Research cross-content (code + papers + media) | Graphify index + OMC deep-research | L3 |
| Onboard onto doc-heavy codebase | Graphify + /gsd-map-codebase + Codebase Onboarding Engineer | L3 |
| Onboard onto a single, code-only repo | Understand Anything `/understand` + `/understand-dashboard` (trial) + /gsd-map-codebase | L2 |
| Pre-refactor dependency check | Graphify query + `lsp_find_references` | L3 |
| Overnight / unsupervised loop hits ambiguity | cortex-queue > `enqueue_decision` + `await_decision` | L2 |
| Financial OHLCV forecast / quant baseline | Kronos > predict (+ backtest) | L2 |
| Fine-tune forecasting model on private data | Kronos > finetune | L3 |
| Financial paper / filing ingestion at scale | QuantMind (trial) | L2 |
| Cross-functional ops | OMC > autopilot > Chief of Staff | L2 |
| **Multi-domain build (≥2 disciplines)** | **OMC > /team > [Specialist A ∥ Specialist B ∥ …] → reconciler** | **L3** |
| Cross-cutting audit (security + perf + a11y) | OMC > /team > parallel domain auditors → /ccg reconciler | L3 |
| Full-stack feature (API + UI + data) | OMC > /team > [Backend Architect ∥ Frontend Developer ∥ Database Optimiser] → /ccg reconciler | L3 |

---

## Notes on building your own

The patterns that have proven valuable across many projects:

- **CCG auto-firing on irreversible actions** — the single biggest catch for "wait, are you sure" moments
- **Sentinel-style checkpoint review** — CCG validates the *plan*, a cross-family critic validates the *diff*. Two different failure modes, two different gates
- **Domain breadth → multi-agent fan-out by default** — prevents single-specialist tunnel vision. Shape is a separate decision from tier
- **The anti-inflation rule** — the log showed ~67% of early routes were L3, most of them reflexive bumps. L3 must name a concrete failure mode L2 would produce
- **`Direct > batched-edits @ L2` for tightly-scoped multi-file work** — when routing overhead exceeds the actual work
- **Three confidences, not one** — "high route, high tier, low spec" is the canonical signal to stop and interview before executing
- **Self-learning log** — at ~30 routes, two patterns auto-surfaced that were being done instinctively but never codified. `cortex hint` started producing useful signal well before the theoretical threshold

Your patterns will be different. The framework is universal; the routes are personal.
