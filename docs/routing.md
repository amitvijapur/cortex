# Routing in depth

The reasoning behind the calibration rules. The [README](../README.md#how-it-works) covers the protocol and the tier table; this is why the tiers behave the way they do.

---

## The anti-inflation rule

**L3 must justify itself against L2, not the other way around.** Picking L3 because the work feels important or is customer-facing is inflation. The route has to name a concrete failure mode L2 would produce, such as *"L2 would skip the verifier pass and this touches auth"*.

Three tests. All "no" means **L2**:

1. **Cost of being wrong.** Does shipping this broken cost money, trust, or production?
2. **Genuine uncertainty.** Is the solution unclear, or does it just need typing out?
3. **Non-trivial verification.** Does proving correctness take more than one read-through?

The rule exists because of measurement. In one audit the first 36 logged routes came out at roughly **67% L3**, mostly reflexive bumping on "customer-facing" or "touches more than two files".

`cortex audit-tiers` lists every L3 and L4 route with its reasoning and outcome, so a tier can be reviewed after the fact. Reclassifying preserves the original tier for the record.

---

## Shape vs depth

Multi-agent work is not an escalation, and treating it as one is the common error. **Depth and breadth are separate decisions.** Tier sets how much rigour a task gets. Shape sets how many independent disciplines it touches.

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

CCG is a tri-model council: Claude, Codex and Gemini. It is one tool the router can reach for rather than a default step.

It fires on pre-plan checks at L3 and L4, irreversible actions (migrations, prod pushes, payments, auth rewrites), security audits, conflicting outputs from two prior agents, and any sign of user uncertainty, which is the strongest trigger. It is skipped on routine work, because three models cost three models' worth of tokens.
