# Routing in depth

The reasoning behind the calibration rules. The [README](../README.md#how-it-works) covers the protocol and the tier table; this is why the tiers behave the way they do.

---

## The anti-inflation rule

The rule I most needed and least wanted.

**L3 must justify itself against L2, not the other way around.** Picking L3 because the work "feels important" or "is customer-facing" is inflation. You have to name a concrete failure mode L2 would produce, like *"L2 would skip the verifier pass and this touches auth"*.

Three questions. All "no" means **L2**:

1. **Cost of being wrong** — does shipping this broken cost money, trust, or prod?
2. **Genuine uncertainty** — is the solution unclear, or do I just need to type it out?
3. **Non-trivial verification** — does proving correctness take more than one read-through?

This exists because the data said so. My first 36 routes came out at roughly **67% L3**, mostly reflexive bumping on "customer-facing" or "touches more than two files". `cortex audit-tiers` lists every L3 and L4 with its reasoning and outcome so you can ask whether L2 would have done; reclassifying preserves the original for the record.

---

## Shape vs depth

The mistake I kept making was treating multi-agent work as an *upgrade*, something you escalate to when a task feels serious. **Shape and tier are orthogonal.** Tier is depth; shape is how many independent disciplines a task touches.

<p align="center"><img src="../assets/fan-out.svg" alt="A cross-domain task fans out to parallel specialists, then converges through a reconciler into one result" width="880"></p>

Two or more independent domains means parallel specialists plus a reconciler is the *correct* shape, at whatever tier the work warrants; a well-scoped L2 fan-out is normal. Running a cross-domain task through one generalist is a routing bug, not a saving. High-stakes fan-outs upgrade the reconciler to a full [council](#ccg-the-council-as-one-tool).

---

## Three confidences

Confidence is not one number. Three things can be independently shaky, each with its own remedy:

| Dimension | The question it answers | If `low` |
|---|---|---|
| `--route-confidence` | Am I picking the right system and pattern? | widen `cortex hint`, or cross-check with a council |
| `--tier-confidence` | Is this really L3, or would L2 have done? | flagged for the next `audit-tiers` pass |
| `--spec-confidence` | Do I actually understand what you want? | **stop before executing** and go interview |

That last one is the strongest trigger in the system. It catches *high route, high tier, low spec*: **"I know exactly which tool to use, I'm just not sure what you asked for."** That is the state in which agents confidently build the wrong thing.

---

## CCG: the council, as one tool

CCG is Claude + Codex + Gemini: the LLM Council pattern, alive and well, demoted from *the architecture* to *one tool the router can reach for*. It fires on pre-plan checks at L3/L4, irreversible actions (migrations, prod pushes, payments, auth rewrites), security audits, conflicting outputs from two prior agents, and any sign of **your** uncertainty, which is the strongest trigger there is. It is skipped on routine work, because three models cost three models' worth of tokens.
