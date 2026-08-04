# eval — consistency tests for the Cortex routing protocol

Phase 1 of the Cortex hardening plan. Two tools, both deliberately narrow in what they
claim.

## What this does and does not establish

These tests answer **"did something break?"** They do not answer **"was that a good
route?"** There is no oracle for routing quality here, and building one needs labelled
data that does not exist yet.

Read that limit literally. A green run means the protocol still behaves the way
cortex.md describes. It does not mean the routing is good, and a suite that quietly
grows into a quality claim would be exactly the kind of false assurance this project
exists to remove.

## route_eval.py

Spawns an isolated headless session per case, captures the routing line, and asserts a
property of it.

```bash
python3 eval/route_eval.py --dry-run          # list cases, spend nothing
python3 eval/route_eval.py                    # full suite, ~$0.50/case
python3 eval/route_eval.py --kind rule --repeat 3
```

Four case kinds, in ascending order of how much they prove:

| Kind | What it proves |
|---|---|
| `canary` | Only recall. The answers are worked examples inside cortex.md, which the model can see. Detects document corruption or a protocol that stopped loading. |
| `rule` | Generalisation. A rule from cortex.md applied to a task the document has never seen. |
| `paired` | A directional property, comparing a transformed task against its own base rather than an absolute tier. |
| `shape` | Whether the Domain-breadth heuristic fires, i.e. fan-out versus a single lane. |

Design decisions worth preserving:

- **One session per case.** Batching would be cheaper and would invalidate the paired
  comparisons, because an earlier answer in the same session anchors a later one.
- **`CORTEX_HOME` is redirected to a throwaway sandbox.** Without it a model following
  the protocol, or a SessionStart hook, appends test routes into the real cortex log and
  silently contaminates the dataset the rest of the plan depends on.
- **The model is pinned and recorded**, alongside the SHA of cortex.md and CLAUDE.md.
  Routing behaviour is a property of model *and* document. Two runs are only comparable
  when those hashes match; a differing hash explains a difference rather than flagging a
  regression.
- **`parse_route` is imported from `bin/cortex`.** A second copy of the grammar here
  would be free to drift from the real one, which is the precise bug class this suite
  exists to catch.
- **Repeats estimate stability, they do not increase sample size.** The statistical unit
  stays the case.
- **Outcomes are `pass` / `fail` / `unstable` / `refused`.** The last two exist because
  collapsing them into `fail` manufactures false protocol violations: a model may
  decline a destructive task, and with no majority across repeats the "modal" route is
  an arbitrary tie-break that another draw would reverse.

## build_retrieval_set.py

Mines the routing log for candidate `(task -> agent)` pairs to evaluate agent retrieval.

```bash
python3 eval/build_retrieval_set.py
```

**Output is an unlabelled worksheet, not a gold set**, for three reasons that would each
invalidate naive use:

1. **Selection bias.** The pairs come from a system whose agent selection is known to be
   salience-driven rather than fitness-driven. They sample what was reachable, not what
   was correct.
2. **Leakage.** Using the same pairs to rewrite agent descriptions *and* to evaluate
   retrieval over those descriptions measures memorisation. Draw the split after
   labelling, and do not read the held-out half while editing descriptions.
3. **Judgement.** Where a route invented a role name that a real agent already covers,
   the correct answer is a decision, not a fact recoverable from the log.

Hard negatives are drawn from the same division as the proposed agent. Random negatives
flatter retrieval, because telling a security agent from a marketing agent is trivial;
same-division confusion is where retrieval actually fails.

### Known limitation: lexical matching is not sufficient

The proposal step ranks by token overlap, weighted toward the agent name. Above roughly
0.5 the suggestions are usable. Below it they are dominated by single-word collisions:
`Grading Specialist` matches Xiaohongshu **Specialist**, and `Dependency Auditor`
matches Paid Media **Auditor** rather than the Application Security Engineer that
actually covers the job.

This is a finding rather than only a defect. If keyword overlap cannot map an invented
label onto the right agent, then a retrieval layer built on keyword search will not
either, and Phase 4 needs semantic matching plus rewritten descriptions rather than a
search box over the current text.
