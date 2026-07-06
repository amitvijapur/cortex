---
description: Triage links dropped into the Cortex inbox via Telegram — fetch, judge against the registry, propose integrations
---

# /cortex-intake

Process the Cortex intake inbox. You drop links to skills, workflows, MCPs, agents, or tools into the dedicated Telegram bot; each becomes a pending row in `~/.claude/cortex-inbox.jsonl`. This command evaluates those pending items and proposes whether to fold them into Cortex.

Follow the propose-and-approve principle: never edit `cortex.md` directly. Draft the change, surface it, and let you approve.

## Steps

1. **Load pending items.**
   Run `python3 ~/.claude/bin/cortex intake list` (add `--json` for structured output). If it prints that the inbox is empty, say so and stop.

2. **For each pending entry, fetch and understand it.**
   Use WebFetch (or Firecrawl for bot-walled pages) on the URL. If the entry has no URL and is just a note, treat the note as the request. Work out what it actually is: a Claude skill, an OMC/GSD workflow, an MCP server, an agent, a design system, a domain model, or something else.

3. **Judge it against the existing registry.** Read `~/.claude/cortex.md` and answer, honestly:
   - Does Cortex already have something that does this? Name the overlap.
   - Does it add a capability that is currently missing, or meaningfully beat an incumbent?
   - If valuable, which registry section and which Decision Shortcut would it slot into, and at what effort tier?
   - What is the install or setup cost, and are there conflicts or risks?
   Give each item a verdict: **integrate**, **maybe** (needs a trial first), or **skip**.

4. **Write a proposal for anything worth integrating.**
   Create a note in `your proposals folder ($CORTEX_OBSIDIAN_ROOT/proposals, or ~/.claude/cortex-proposals by default)` named `YYYY-MM-DD--intake--<slug>.md` with YAML frontmatter (`tags: [cortex, proposal, intake]`, `status: pending`, `source_url:`). In the body: what it is, why it adds value, the exact `cortex.md` edit you propose (registry section + Decision Shortcut row + tier), and setup steps. Draft the edit but do not apply it.

5. **Report back and resolve.**
   Summarise the batch for you in the session (one line per item with its verdict). Then mark each item so it is not re-triaged:
   - `python3 ~/.claude/bin/cortex intake resolve <id> --status accepted --note "<verdict>"` for integrate/maybe (proposal written, awaiting approval)
   - `python3 ~/.claude/bin/cortex intake resolve <id> --status rejected --note "<reason>"` for skip
   Use `integrated` only after you approve and the `cortex.md` edit has actually landed.

6. **Ping Telegram (optional).**
   If useful, send you a one-line verdict per item back through the intake bot chat so he sees the outcome without opening a session.

## Notes
- Keep verdicts skeptical. The point is to protect Cortex from bloat, not to say yes to everything. A tool that duplicates an incumbent is a skip even if it is good.
- Batch related items. If three dropped links are all React animation tools, judge them against each other, not just against the registry.
