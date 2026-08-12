# What the checks prove, and what they don't

The [README](../README.md#checking-the-router) covers what `eval/` measures. This is the honest accounting of its limits, and the record of what it has killed. For how each script works, see [`eval/README.md`](../eval/README.md).

---

## What this does not establish

These tests answer *"did something break?"*, not *"was that a good route?"* There is no oracle for routing quality here, and building one needs labelled data that does not exist yet. A suite that quietly grew into a quality claim would be exactly the false assurance this was built to remove.

**The floors are targets, not pre-registrations.** They were chosen with the current numbers visible, which the thresholds file admits in its own header, and they sit *below* where the system runs today so they catch regression rather than certifying the present as good. **A floor is not a goal** either: `hint_before_route` floors at 25% against a target of 60%, and 25% is not an endorsement of 29%.

---

## What the harness has rejected

A test suite that has never contradicted its author is decoration. Two things this one killed:

- **A tuned BM25F ranker for agent retrieval.** It beat the baseline on the development set, then lost on held-out data. The corpus hygiene fixes shipped; the ranker did not.
- **A capability-confinement layer for the intake worker.** Built, then removed once the evidence showed it defended against an adversary that does not exist for a personal tool, while breaking credentials and plugin hooks. The correctness half survived: approvals are bound to a content hash, and a build reports success only when the target file actually changed, not when the model says it did.

It has also caught its own author. Changing a default ranker silently rewrote what every evaluation row was measuring, because no result recorded which ranker produced it.
