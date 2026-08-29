# eval — checks for the Cortex routing protocol

A router that describes its own reasoning is easy to build and easy to fool, because the
reasoning is generated text. It can stay articulate while the behaviour underneath drifts.
Everything here exists to make that difference observable.

## What this does and does not establish

These tests answer **"did something break?"** They do not answer **"was that a good
route?"** There is no oracle for routing quality here, and building one needs labelled data
that does not exist yet.

Read that limit literally. A green run means the protocol still behaves the way cortex.md
describes. It does not mean the routing is good, and a suite that quietly grew into a
quality claim would be exactly the kind of false assurance this project exists to remove.

---

## The standing check: what does the no-model baseline score?

Four improvements to retrieval have now been proposed here, and all four lost:

| Proposal | Beaten by | Margin |
|---|---|---|
| Tuned BM25F ranker | the untuned baseline, on held-out data | lost after winning on dev |
| 232 agent description rewrites | the original descriptions, on held-out data | lost |
| Semantic embeddings for `hint` | showing the 5 most recent routes in the same class | ~16x |
| Graph layer over the routing log | the same recency baseline | +1 case, p = 1.0 |

The shape is identical every time: a better **scoring function** offered for a retrieval
problem whose bottleneck was somewhere else, compared against whichever baseline made it
look good. Each would have been caught in an afternoon by asking what the version with no
model and no new data structure scores on the same denominator.

So that question is now mandatory before any retrieval change is built, not after. If the
trivial baseline has not been measured, the proposal is not ready to evaluate. `hint_arms.py`
exists to make running it cheap.

The fourth entry is worth singling out because the losing hypothesis was a good one.
`tier_reason` is populated on every row and visibly encodes the shape vocabulary the routing
protocol says drives a route — "reversible", "single domain", "no prod blast radius". Given
oracle access to a query's own `tier_reason`, which cheats, retrieving on shape still scored
*below* plain recency. Being able to tell a good story about why a change should work is not
correlated with the change working, which is the whole reason this directory exists.

---

## Adherence — is the protocol actually being followed?

`score_adherence.py` scores every route in the log against the floors in
`adherence-thresholds.json`.

```bash
python3 eval/score_adherence.py --check     # non-zero exit on a breach
python3 eval/score_adherence.py --summary
python3 eval/score_adherence.py --show hint_before_route
```

Three things about the thresholds are worth knowing before you trust them, and all three
are stated in the file's own header:

- **They are targets, not pre-registrations.** They were chosen with the current numbers
  already visible. Calling them pre-registered would be a fiction.
- **A floor is not a goal.** Floors sit *below* where the system runs today so they catch
  regression, rather than certifying the present state as good. `hint_before_route` has a
  floor of 25% and a target of 60%; the floor is not an endorsement of 29%.
- **Only metrics that can be gated are gated.** `agent_field_populated` is excluded because
  it is knowably wrong on fan-out lines, and `session_routed` because it has no single
  value by construction.

Correction events are folded in through `bin/cortex`'s own `collapse()` rather than a
second implementation, for the same reason `route_eval.py` imports `parse_route`: a private
copy is free to drift from the real one.

## Routing consistency — does the same task still route the same way?

`route_eval.py` puts a task to a headless session, captures the routing line, and asserts a
property of it.

```bash
python3 eval/route_eval.py --dry-run          # list cases, spend nothing
python3 eval/route_eval.py                    # full suite, ~$0.50/case
python3 eval/route_eval.py --kind rule --repeat 3
python3 eval/route_eval.py --if-changed       # skip when no input hash moved
```

Four case kinds, in ascending order of how much they prove:

| Kind | What it proves |
|---|---|
| `canary` | Only recall. The answers are worked examples inside cortex.md, which the model can see. Detects document corruption or a protocol that stopped loading. |
| `rule` | Generalisation. A rule from cortex.md applied to a task the document has never seen. |
| `paired` | A directional property, comparing a transformed task against its own base rather than an absolute tier. |
| `shape` | Whether the Domain-breadth heuristic fires, i.e. fan-out versus a single lane. |

Design decisions worth preserving:

- **Paired cases are never batched.** Independent cases do share one session by default,
  because that is much cheaper and nothing about them depends on isolation; any the model
  drops are re-run individually. Paired cases are the exception and always get their own
  session, because an earlier answer in a shared session anchors a later one, which is
  precisely what a paired comparison must not allow. `--no-batch` isolates everything.
- **`CORTEX_HOME` is redirected to a throwaway sandbox.** Without it a model following the
  protocol, or a SessionStart hook, appends test routes into the real cortex log and
  silently contaminates the dataset the rest of the work depends on.
- **The model is pinned and recorded**, alongside the SHA of cortex.md and CLAUDE.md.
  Routing behaviour is a property of model *and* document. Two runs are only comparable when
  those hashes match; a differing hash explains a difference rather than flagging a
  regression.
- **`parse_route` is imported from `bin/cortex`.** A second copy of the grammar here would
  be free to drift from the real one, which is the precise bug class this suite exists to
  catch.
- **Repeats estimate stability, they do not increase sample size.** The statistical unit
  stays the case.
- **Outcomes are `pass` / `fail` / `unstable` / `refused`.** The last two exist because
  collapsing them into `fail` manufactures false protocol violations: a model may decline a
  destructive task, and with no majority across repeats the "modal" route is an arbitrary
  tie-break that another draw would reverse.
- **There is a spend ceiling.** `--max-spend` exists because the first unbounded run cost
  $13.

## Replay — comparing two versions of the protocol

`build_replay_set.py` freezes a paired set of past tasks; `replay_compare.py` runs both
arms and diffs them; `replay_priority.py` ranks which items are worth labelling by hand
first.

Paired replay is used rather than an unpaired comparison of the whole log because the
sample sizes are not close: a detectable unpaired effect needs hundreds of routes per arm,
where a paired design needs tens.

## Retrieval — can the right agent be found at all?

`build_retrieval_set.py` mines the log for candidate `(task → agent)` pairs.
`eval_retrieval.py` scores retrieval over them. `agent_search.py` is the ranker under test.
`apply_descriptions.py` writes proposed description rewrites into the roster, backing up
every file first.

**The mined output is an unlabelled worksheet, not a gold set**, for three reasons that
would each invalidate naive use:

1. **Selection bias.** The pairs come from a system whose agent selection is known to be
   salience-driven rather than fitness-driven. They sample what was reachable, not what was
   correct.
2. **Leakage.** Using the same pairs to rewrite agent descriptions *and* to evaluate
   retrieval over those descriptions measures memorisation. Draw the split after labelling,
   and do not read the held-out half while editing descriptions.
3. **Judgement.** Where a route invented a role name that a real agent already covers, the
   correct answer is a decision, not a fact recoverable from the log.

Hard negatives are drawn from the same division as the proposed agent. Random negatives
flatter retrieval, because telling a security agent from a marketing agent is trivial;
same-division confusion is where retrieval actually fails.

### What the retrieval work rejected

A tuned BM25F ranker beat the baseline on the development set and **lost on held-out
data**. The corpus hygiene fixes shipped; the ranker did not.

The harness also caught its own author: changing the default ranker silently rewrote what
every evaluation row was measuring, because a result did not record which ranker produced
it. Rankers are now named explicitly at the call site.

## Hint retrieval — is better ranking even the fix?

`hint_baseline.py`, `hint_ceiling.py` and `hint_headroom.py` exist because "semantic search
would obviously beat keyword overlap" is exactly the kind of plausible claim that had
already lost twice.

- **`hint_baseline.py`** replays the log chronologically. For entry *i* the pool is entries
  `0..i-1`, which is what `hint` could actually have seen at that moment. Full leave-one-out
  over the whole log leaks the future and inflates coverage.
- **`hint_ceiling.py`** runs an ORACLE retriever that is allowed to look at the answer and
  return the most useful prior entry. Where the oracle cannot help either, the query is
  unreachable by *any* retriever and better ranking is not the fix.
- **`hint_headroom.py`** compares Jaccard against the majority-tier baseline **on the same
  matched subset** rather than across all queries. Comparing across all queries is the exact
  trap that flattered BM25F.

The finding: a meaningful share of queries are unreachable by any lexical retriever, so the
cap is vocabulary rather than ranking. That result is what gates whether the embedding work
is worth doing.

### One denominator for every proposal

`hint_arms.py` exists because the scripts above were each written to assess one proposal,
and a proposal assessed against its own chosen baseline will tend to win. It replays every
arm — the shipped Jaccard gate, recency, recency plus project, shape-based retrieval, and a
graph retriever — over the same queries against the same prior pool, and reports the same
four numbers for each.

Two conventions in it are load-bearing:

- **The graph arm is restricted to edges a cold query legally has.** When `hint` runs, the
  session has a task, a class and a project, and does not yet have a route, tier or agent.
  Traversing a "shares an agent with" edge out of the query would be reading the answer.
  Any arm that scores well by using a field it would not have at call time is measuring
  nothing.
- **A number produced by an uncommitted script is not a baseline.** The MLX decision
  recorded 23.8% for recency and treated it as the bar for the follow-up work. It does not
  reproduce: the same window gives 19.2% literally, 20.8% deduplicating by route, 25.4% at a
  looser label. None of those is wrong, and the figure was never pinned to code that says
  which one it meant. The `LABEL SENSITIVITY` block prints the grid so the next comparison
  starts from a stated definition.

`graph_density.py` answers the prior question of whether the log contains a graph at all. It
counts the edges each proposed affordance would get, and checks whether traversal depth does
anything: for a graph joined on one shared attribute, the 1-hop and 2-hop neighbourhoods are
the same set, which is a property of the construction rather than of this dataset and cannot
be fixed with more rows.

## Registry evidence — unused, or unreachable?

`registry_reachability.py` scores every extended-registry entry on three axes that a single
usage count silently merges: is it **on disk**, is it **reachable** from a Decision Shortcuts
row, and is it **used** anywhere in the log.

Only the installed-and-reachable-and-unused cell is evidence about a tool. An entry the
router was never told about, or one whose install path does not exist, has a usage count of
zero for reasons the tool had no way to influence. Both cases were live: two entries have no
shortcut row, and the registry claimed a design-systems library at a path that is not there.

Aliases are hand-curated rather than inferred, because a fuzzy match that counts the word
"data" as a use of the `data` plugin manufactures exactly the false confidence the rest of
this directory exists to prevent.

## Supporting files

| File | What it is |
|---|---|
| `test_cortex_cli.py` | Behavioural tests for `bin/cortex`. Run it directly (`python3 eval/test_cortex_cli.py`), not under pytest — it has its own runner. |
| `cases.json` | The `route_eval.py` case definitions. |
| `derive_outcomes.py` | Recovers outcomes from transcripts for routes where none was recorded live. |
| `agent_invocation_probe.py` | Checks whether the agent named in a routing line was the agent actually invoked. |
| `worksheet_md.py` | Renders labelling worksheets for the pairs that need a human decision. |
