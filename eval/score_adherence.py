#!/usr/bin/env python3
"""score_adherence — per-step conformance to the Cortex routing protocol.

WHAT THIS MEASURES
    For each step of the protocol in ~/.claude/cortex.md — hint, declare, tier, agent,
    confidence, outcome — how often the step was actually performed. Every number is a
    ratio whose numerator and denominator are named in the output, together with what was
    excluded from the denominator and why.

WHAT IT DOES NOT MEASURE
    Whether routing *worked*. A perfectly adhered-to route can be the wrong route, and a
    skipped protocol can precede excellent work. This file scores ceremony, not outcomes.
    derive_outcomes.py is the file that looks for evidence about how routes went, and it
    is deliberately kept separate.

    It also does not measure whether a skip was *correct*. The protocol permits skipping
    trivial work, and nothing in the artifacts records "I judged this trivial". A session
    with no route is either a legitimate skip or a protocol miss and this file cannot tell
    them apart. That is the whole reason the coverage metric is banded rather than scored.

THE DENOMINATOR PROBLEM, AND HOW IT IS HANDLED
    Two of these questions have clean denominators and one does not.

    Clean — "given that a route was declared, was the rest of the ceremony performed?"
    The denominator is the set of logged routes. Nothing is conditioned on the behaviour
    being measured, because declaring the route and (say) naming an agent are separate
    acts. These are reported as `measured`.

    Also clean, with a stated coverage caveat — "was `hint` run before this route?" The
    denominator is the set of routes whose creating command was found in a transcript.
    That is a *subset* of routes, and a biased one (see COVERAGE below), so the metric is
    reported as `measured` over an explicitly named subset, never over the whole log.

    Not clean — "did substantive sessions route at all?" The denominator is the set of
    sessions where the protocol *should* have applied, which is exactly the thing nobody
    recorded. "All sessions" is far too wide: the Skip protocol makes many sessions
    legitimately route-free. "Sessions that logged a route" is circular. So this one is
    reported as `banded`: a ladder of increasingly strict substantiveness thresholds, each
    with its own measured ratio, and the band is the span between the loosest and the
    strictest. Both endpoints are facts; the assumption is only that the truth lies
    between them, and the assumption that would break each endpoint is printed with it.

    A metric that is neither measured nor honestly bandable is dropped. `dropped` metrics
    are listed in the output with the reason, so that dropping is visible rather than
    silent.

COVERAGE — the limit that governs every transcript-derived number
    A route is joined to a transcript by the same mechanism derive_outcomes.py uses, and
    that module is imported rather than reimplemented so the two files cannot disagree
    about which window belongs to which route. The join finds the `cortex log-line` shell
    command that created the row.

    That join is heavily time-biased, and the bias is not subtle:

        2026-04   32 rows    0 attributable   (0%)
        2026-05    7 rows    1 attributable  (14%)
        2026-06    5 rows    0 attributable   (0%)
        2026-07   85 rows   71 attributable  (84%)
        2026-08   14 rows   12 attributable  (86%)

    Transcripts older than July have been pruned — the whole of April survives as 33
    events. So every transcript-derived number here is a statement about July and August
    2026, not about the log's history, and it is reported that way. The 44 pre-July rows
    are not scored on those metrics and are excluded as not measurable, not counted as
    failures.

    `session_ref` — the field that makes this join exact — exists on 3 of 144 rows. It is
    used when present and contributes essentially nothing today. No historical row is
    given an attribution it cannot support.

WHAT IT FOUND, 2026-08-06, over 143 route rows and 154 transcript sessions
    One row was excluded before scoring: the log has gained an event-typed schema and now
    carries an `event: "outcome"` row that is not a route. Scoring it would have invented
    five violations out of a schema change.

    Measured, log-only (denominator = all 143 route rows unless stated):

        tier_declared                 143/143 100.0%
        confidence_declared           106/107  99.1%  (denominator starts at the first row
                                                        carrying the field; 36 earlier rows
                                                        excluded — the field did not exist)
        outcome_recorded              128/143  89.5%
        agent_field_populated          93/143  65.0%  → 73/86 (84.9%) excluding `Direct`
                                                        rows, which have no agent by
                                                        design. At least 9 more name an
                                                        agent inside `pattern`, which the
                                                        parser folds on fan-out lines, so
                                                        even 84.9% understates.
        outcome_recorded_live          90/143  62.9%  (excludes 38 bulk-backfilled)

    Measured, transcript-derived (denominator = the 84 anchor-attributed routes, which are
    effectively all July-August):

        outcome_is_observation         55/71   77.5%  of routes carrying an outcome, the
                                                        share with no evidence the label
                                                        was ceremony. 51 of those 55 have
                                                        a `cortex outcome` command inside
                                                        their own window at a median 11
                                                        minutes after declaration.
        hint_before_route              24/84   28.6%
        hint_could_inform_route        19/84   22.6%  5 of the 24 ran `hint` inside the
                                                        same shell command as the
                                                        declaration, where the routing line
                                                        was already written.

    The hint result is the one worth dwelling on, because framing moves it by 2x. Read per
    session — did this session ever run hint — the same corpus gives 16/25 = 64%, which
    reproduces an earlier hand-count of transcripts almost exactly. Read per route, as
    protocol step 3 is written, it is 28.6%. The difference is 42 routes declared after a
    hint that was run for an *earlier* task in the same session. Neither number is wrong;
    quoting either without saying which is.

    Banded — did substantive sessions route at all?

        >=1 turn                       27/46   58.7%
        >=2 turns                      27/44   61.4%
        >=3 turns, >=1 write           26/34   76.5%
        >=5 turns, >=3 writes          20/27   74.1%
        >=8 turns, >=5 writes          19/23   82.6%

        Band: 59%–83%, after excluding 108 sessions that were not Amit talking to Claude
        — intake workers, the weekly scout, hook-spawned security reviewers, the eval
        harness's own replay probes, the Almanac bot. That exclusion is the difference
        between a defensible band and a fiction: leaving those in produces a floor of 22%,
        which measures how many robots failed to route.

        Hand-adjudicated for calibration, not as a metric: of the 19 eligible sessions
        with no route, roughly 8 look like genuine misses (a folder audit over 38 turns, a
        Telegram bot build, two multi-turn debugging sessions, a client quote rebuild),
        roughly 9 look like correct skips under the Skip protocol (resume a session, pull
        a repo, open a file, place a note), and 2 are arguable. That puts a hand-judged
        point estimate near 71-77%, inside the band. The band is the reportable result;
        the point estimate is one person's reading of 19 sessions.

    The shape matters more than any single figure. The ceremony *inside* a declared route
    is near-total (tier 100%, confidence 99%). The step *before* the route — the advisory
    hint that is supposed to inform the choice — is performed on under a third of routes.
    Adherence is not one number and must never be reported as one.

WHAT IS SAFE TO GATE ON LATER
    Thresholds are Amit's to set and none are set here. But the metrics differ in whether
    they *could* carry a gate at all, and that is a property of the measurement:

    Gateable. Denominator is exact, the input is the log alone, and the number cannot move
    because a transcript was pruned or a session was misclassified:
        tier_declared, outcome_recorded, outcome_recorded_live, confidence_declared.

    Gateable with the coverage caveat attached. Denominator is exact over the attributed
    subset, and the classification is a string being present or absent in a preserved shell
    command — the same precision derive_outcomes hand-checked at 15/15. Safe to gate as
    long as the gate is understood to cover recent routes only, and as long as a drop in
    the *attribution rate* is not read as a drop in adherence:
        hint_before_route, hint_could_inform_route, outcome_is_observation.

    Indicative only, never gate:
        agent_field_populated — checks a field, and the field is knowably wrong on fan-out
            lines where the parser folds the agent into `pattern`.
        hint_query_matched_task — depends on a similarity threshold that is a knob.
        session_routed — has no single value by construction. A gate would be a gate on a
            chosen threshold, which is the false precision this file exists to avoid.

READ-ONLY
    Reads the cortex log, the transcripts, and nothing else. Writes exactly one file under
    the state dir. It never writes to the cortex log and never touches a transcript.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

# The attribution machinery is imported, not reimplemented. Two files that each decide
# for themselves which transcript window belongs to which route will eventually disagree,
# and then neither can be trusted. derive_outcomes owns that decision; this file consumes
# it. Importing is safe: the module guards its own entry point.
import derive_outcomes as D  # noqa: E402

CLAUDE_DIR = D.CLAUDE_DIR
LOG_PATH = D.LOG_PATH
PROJECTS_DIR = D.PROJECTS_DIR
DEFAULT_OUT = REPO / ".omc" / "state" / "adherence" / "adherence.jsonl"

SCHEMA_VERSION = "adherence-v1"

HINT_RE = re.compile(r"cortex\s+hint\s+")

# A `cortex` command run against a temporary CORTEX_HOME is the CLI's own test suite
# exercising itself, not a protocol act. One such command exists in the corpus and it
# would otherwise register as a route declaration in a session that was testing the tool.
TEST_HARNESS_RE = re.compile(r"CORTEX_HOME\s*=")

# Sessions started by automation rather than by Amit. The protocol is a thing Claude does
# for Amit in an interactive session; a headless intake worker or the weekly scout has no
# route to declare, and leaving them in the denominator would manufacture non-compliance.
# Matched on the opening user turn, which is the injected prompt, plus the directories
# those jobs run in. Every exclusion is counted by reason in the output.
AUTOMATION_PREAMBLES = [
    (r"^You are the Cortex intake", "cortex-intake worker"),
    (r"^You are Amit's Cortex assistant", "cortex-intake ask worker"),
    (r"^You are the weekly Cortex ecosystem scout", "weekly ecosystem scout"),
    (r"^You are Amit's Desktop Almanac", "almanac bot (read-only)"),
    (r"^Route only\. Do not perform the task", "route_eval replay probe"),
    (r"^Review this change for security vulnerabilities", "hook-spawned security review"),
    (r"^Reply with exactly:", "harness liveness probe"),
    (r"^Do exactly two things with the Write tool", "agent-invocation probe"),
    (r"^You previously flagged these candidate vulnerabilities", "hook-spawned security review"),
    (r"^Route each task below independently under the Cortex protocol", "route_eval replay probe"),
    (r"^Think briefly about what 2\+2 is", "harness liveness probe"),
]
AUTOMATION_DIRS = [
    ("-Users-amit--claude-cortex-intake", "cortex-intake project dir"),
    ("-Users-amit-Desktop-cc-scratch-test", "eval probe scratch dir"),
    ("-private-tmp", "eval probe temp dir"),
    ("-private-var-folders", "eval probe temp dir"),
]

# The substantiveness ladder for the banded coverage metric. Each rung is a guess about
# where "trivial" ends, and the point of showing all of them is that no rung is privileged.
# Read the spread, not any single row.
SUBSTANTIVE_LADDER = [
    (1, 0, "any session with a typed user turn"),
    (2, 0, "at least one follow-up turn"),
    (3, 1, "multi-turn and touched a file"),
    (5, 3, "sustained work: 5+ turns, 3+ file writes"),
    (8, 5, "unmistakably a project: 8+ turns, 5+ file writes"),
]

# Token overlap at or above this fraction of the task's tokens counts a `hint` query as
# being about the same task. It is a knob, which is why it governs a *refinement* metric
# reported alongside its unthresholded parent (`hint_before_route`) rather than replacing
# it. Both numbers are printed so the knob's effect is visible.
QUERY_OVERLAP = 0.5


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def norm(text):
    return " ".join((text or "").lower().split())


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def iso(dt):
    return D.iso(dt)


def ratio(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def metric(mid, status, question, numerator=None, denominator=None, *,
           excluded=None, note="", detail=None, band=None):
    """One reported number, with everything a reader needs to audit it.

    `status` is load-bearing and only ever takes three values:
      measured       — numerator and denominator are both counts of things, and the
                       denominator does not condition on the behaviour being scored.
      banded         — the denominator is a judgement call; `band` holds the span and the
                       assumptions that would break each end.
      dropped        — not reliably measurable; `note` says why. Kept in the output so
                       that a dropped metric is visible rather than quietly missing.
    A `banded` or `dropped` metric must never be printed as if it were `measured`.
    """
    return {
        "id": mid,
        "status": status,
        "question": question,
        "numerator": numerator,
        "denominator": denominator,
        "value": ratio(numerator, denominator) if status == "measured" else None,
        "excluded": excluded or {},
        "band": band,
        "detail": detail,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Log-only metrics
#
# These need no transcript and cover all 144 rows, which makes them the only adherence
# numbers that describe the log's whole history. They are also the weakest kind of
# evidence available here, because they check that a *field was filled in*, not that the
# thinking behind the field happened. `tier_declared` at 99% means the CLI required a
# tier, not that the tier was calibrated.
# ---------------------------------------------------------------------------
TIER_RE = re.compile(r"^L[1-4]$")

# The log has an event-typed schema and carries rows that are not routes — an
# `event: "outcome"` row settles an earlier route and has no task, tier, or agent of its
# own. Scoring it as a route would invent five separate protocol violations out of a
# schema change, which is precisely the manufactured-finding failure this file is built to
# avoid. The test is imported rather than restated for the same reason attribution is: the
# two files must not be able to disagree about what a route is.
is_route = D.is_route


# The routing line is parsed into system / pattern / agent by `cortex log-line`. When the
# line describes a fan-out or a hand-off — "[executor(sonnet) ∥ research] → Fable QC" —
# the actors land in `pattern` and `agent` stays empty even though the line named them.
# These markers identify that case. They give a *lower bound* on how far the agent field
# undercounts; they are never used to inflate the headline ratio.
AGENT_IN_PATTERN_RE = re.compile(r"[→∥]|\[")


def log_metrics(rows):
    out = []
    total = len(rows)

    tiered = sum(1 for r in rows if TIER_RE.match(str(r.get("tier") or "")))
    out.append(metric(
        "tier_declared", "measured",
        "was an effort tier L1-L4 recorded on the route?",
        tiered, total,
        note="Records that the field is populated. It cannot see whether the tier was "
             "calibrated or reflexively set, which is the failure mode "
             "`cortex audit-tiers` exists for."))

    named = sum(1 for r in rows if (r.get("agent") or "").strip())
    direct = [r for r in rows if str(r.get("system") or "").startswith("Direct")]
    direct_unnamed = sum(1 for r in direct if not (r.get("agent") or "").strip())
    scoped_total = total - len(direct)
    scoped_named = named - (len(direct) - direct_unnamed)
    parser_loss = sum(1 for r in rows
                      if not (r.get("agent") or "").strip()
                      and AGENT_IN_PATTERN_RE.search(str(r.get("pattern") or "")))
    out.append(metric(
        "agent_field_populated", "measured",
        "was the route's `agent` field filled in?",
        named, total,
        detail={"direct_execution_rows": len(direct),
                "direct_rows_without_agent": direct_unnamed,
                "excluding_direct": {"numerator": scoped_named,
                                     "denominator": scoped_total,
                                     "value": ratio(scoped_named, scoped_total)},
                "agent_named_in_pattern_instead": parser_loss},
        note="Named for what it actually checks: a field being populated, not an agent "
             "being chosen. It is the weakest metric here and should not be gated on, for "
             "two reasons that both push the same way. Rows whose system is Direct "
             "execution have no agent by design, so the `excluding_direct` reading is the "
             "fairer one. And when the routing line describes a fan-out, `log-line` parses "
             "the actors into `pattern` and leaves `agent` empty — at least "
             f"{parser_loss} rows name an agent in the line and score as a miss here. "
             "Both corrections raise the true figure; neither is applied to the headline, "
             "because the second is a lower bound rather than a count."))

    # The three-confidence flags were added partway through the log's life. Scoring rows
    # written before the field existed would be scoring the past against a rule that did
    # not yet apply, so the denominator starts at the first row that carries the key.
    first_conf = next((i for i, r in enumerate(rows) if "route_confidence" in r), None)
    if first_conf is None:
        out.append(metric("confidence_declared", "dropped",
                          "were the three confidence flags declared?",
                          note="no row carries the field"))
    else:
        eligible = rows[first_conf:]
        have = sum(1 for r in eligible
                   if r.get("route_confidence") and r.get("tier_confidence")
                   and r.get("spec_confidence"))
        out.append(metric(
            "confidence_declared", "measured",
            "were all three confidence dimensions declared on the route?",
            have, len(eligible),
            excluded={"rows predating the field": first_conf},
            detail={"field_first_seen": eligible[0].get("ts")},
            note="Denominator starts at the first row carrying `route_confidence`; the "
                 f"{first_conf} earlier rows are excluded because the field did not exist "
                 "when they were written, not because they failed."))

    recorded = sum(1 for r in rows if r.get("outcome"))
    backfilled = sum(1 for r in rows if r.get("outcome_backfilled"))
    live = sum(1 for r in rows if r.get("outcome") and not r.get("outcome_backfilled"))
    out.append(metric(
        "outcome_recorded", "measured",
        "was any outcome recorded for the route?",
        recorded, total,
        detail={"backfilled_in_bulk": backfilled},
        note="Counts the field being non-null by any means, including the bulk backfill "
             "of 2026-07-10. See outcome_recorded_live for the stricter reading."))
    out.append(metric(
        "outcome_recorded_live", "measured",
        "was an outcome recorded other than by bulk backfill?",
        live, total,
        detail={"backfilled_in_bulk": backfilled},
        note="`outcome_backfilled` is the row's own admission that its verdict was "
             "assigned retroactively in a sweep rather than observed at task end. This is "
             "self-reported and therefore only a lower bound on ceremony: a route can be "
             "unflagged and still have had its outcome stamped without observation, which "
             "is what outcome_is_observation goes after with transcript evidence."))
    return out


# ---------------------------------------------------------------------------
# Transcript-derived metrics
# ---------------------------------------------------------------------------
def hint_queries(command):
    """Every task string passed to `cortex hint` in one shell command."""
    out = []
    for match in HINT_RE.finditer(command):
        parts = D.split_args(command[match.end():])
        if parts and not parts[0].startswith("-"):
            out.append(parts[0])
    return out


def hint_check(row, attribution, sessions, anchor_times):
    """Did `cortex hint` run in this route's own pre-declaration window?

    The window runs from the previous route declaration in the same session (or the start
    of the session) up to this route's declaration. Using the previous *declaration* as
    the lower bound rather than the session start is what makes this per-route: a session
    that ran hint once and then declared five routes gets one compliant route and four
    non-compliant ones, which is what the protocol says — step 3 is per task, not per
    session. Scoring it per session, as the earlier hand-count did, reads ~2x higher.

    Returns None when the route could not be attributed at all, which is the difference
    between "did not run hint" and "cannot tell".
    """
    session_id = attribution.get("session")
    anchor = attribution.get("start")
    if attribution.get("method") not in ("anchor-command", "anchor-command+ts"):
        return None
    if not session_id or anchor is None:
        return None

    earlier = [t for t in anchor_times.get(session_id, []) if t < anchor]
    lower = max(earlier) if earlier else None

    hits = []
    for event in sessions[session_id]["events"]:
        if event.kind != "tool_use" or not event.cmd:
            continue
        if "cortex hint" not in event.cmd or TEST_HARNESS_RE.search(event.cmd):
            continue
        if event.ts > anchor or (lower is not None and event.ts <= lower):
            continue
        hits.append(event)

    # A hint anywhere earlier in the session, including before the previous route. This is
    # not compliance for *this* route, but it is what a session-level reading counts, and
    # recording it is what lets the two readings be reconciled instead of argued about.
    earlier_in_session = any(
        event.kind == "tool_use" and event.cmd and "cortex hint" in event.cmd
        and not TEST_HARNESS_RE.search(event.cmd) and event.ts < anchor
        for event in sessions[session_id]["events"])

    if not hits:
        return {"ran": False, "could_inform": False, "query_matched": None,
                "earlier_in_session": earlier_in_session,
                "evidence": None, "window_start": iso(lower), "anchor": iso(anchor)}

    # A hint issued inside the same shell command as the declaration cannot have informed
    # the declaration: the routing line was already written when the command was composed.
    # Same argument, and same precision, as derive_outcomes' outcome_stamped_at_declaration
    # — a string either is or is not present in a preserved command.
    same_command = [e for e in hits if "cortex log" in e.cmd]
    could_inform = len(same_command) < len(hits)

    task = row.get("task") or ""
    queries = [q for e in hits for q in hint_queries(e.cmd)]
    matched = None
    if queries:
        task_tokens = tokens(task)
        exact = any(norm(q) == norm(task) for q in queries)
        overlap = any(
            task_tokens and len(tokens(q) & task_tokens) / len(task_tokens) >= QUERY_OVERLAP
            for q in queries)
        matched = "exact" if exact else ("overlap" if overlap else "unrelated")

    chosen = next((e for e in hits if "cortex log" not in e.cmd), hits[0])
    index = HINT_RE.search(chosen.cmd)
    return {"ran": True, "could_inform": could_inform, "query_matched": matched,
            "earlier_in_session": True, "queries": queries[:3],
            "evidence": D.excerpt(chosen.cmd, index, radius=120),
            "hint_ts": iso(chosen.ts),
            "window_start": iso(lower), "anchor": iso(anchor)}


def outcome_command_lag(sessions, attribution):
    """Minutes from this route's declaration to the first `cortex outcome` command inside
    its window, or None if there is none.

    Supporting context for the `observation` class, not a metric. `cortex outcome` closes
    the most recent still-open route for the project, so a command inside this window is
    *consistent with* it settling this route but does not prove it — in a command that
    both closes the previous route and declares this one, the lag is zero and the verdict
    belonged to the predecessor. Read the distribution, not any single value.
    """
    session_id = attribution.get("session")
    start, end = attribution.get("start"), attribution.get("end")
    if not session_id or start is None or session_id not in sessions:
        return None
    for event in sessions[session_id]["events"]:
        if event.kind != "tool_use" or not event.cmd:
            continue
        if not D.OUTCOME_RE.search(event.cmd):
            continue
        if start <= event.ts <= (end or event.ts):
            return round((event.ts - start).total_seconds() / 60, 1)
    return None


def outcome_provenance(row, sessions, attribution):
    """Classify how this route's recorded outcome came to exist.

    Four buckets, in order of how much the label can be trusted:
      none        — no outcome recorded at all
      backfilled  — the row says it was assigned in the bulk sweep
      ceremony    — derive_outcomes found the outcome stamped within 90s of the route's
                    own declaration, or batched into the shell command that declared the
                    *next* route. Either way it settled a protocol step rather than
                    reporting an observation.
      observation — an outcome with none of the above against it. This is the weakest of
                    the four claims and deserves saying plainly: it means no evidence of
                    ceremony was found, not that the outcome was verified.
    """
    if not row.get("outcome"):
        return "none", []
    if row.get("outcome_backfilled"):
        return "backfilled", []
    findings = D.signal_label_provenance(row, sessions, attribution)
    if findings:
        return "ceremony", findings
    return "observation", []


def transcript_metrics(records):
    """Metrics over the anchor-attributed subset. `records` are per-route rows already
    carrying their hint check and provenance class."""
    out = []
    attributed = [r for r in records if r["hint"] is not None]
    total = len(attributed)
    unattributed = len(records) - total

    ran = sum(1 for r in attributed if r["hint"]["ran"])
    informed = sum(1 for r in attributed if r["hint"]["could_inform"])
    stale = sum(1 for r in attributed if not r["hint"]["ran"] and r["hint"]["earlier_in_session"])
    routed_sessions = {r["session"] for r in attributed}
    sessions_with_hint = {r["session"] for r in attributed
                          if r["hint"]["ran"] or r["hint"]["earlier_in_session"]}
    out.append(metric(
        "hint_before_route", "measured",
        "was `cortex hint` run between the previous route and this one?",
        ran, total,
        excluded={"routes with no transcript join": unattributed},
        detail={"of_which_same_shell_command_as_declaration": ran - informed,
                "routes_with_a_hint_earlier_in_the_session_but_not_their_own": stale,
                "session_level_reading": {
                    "numerator": len(sessions_with_hint),
                    "denominator": len(routed_sessions),
                    "value": ratio(len(sessions_with_hint), len(routed_sessions))}},
        note="Per route, not per session, because protocol step 3 is per task. This is the "
             "single most important framing choice in the file and it moves the answer by "
             "roughly 2x: read per session — did this session ever run hint — the same "
             "corpus gives a much higher figure, which is what an earlier hand-count of "
             "transcripts reported. Both are correct answers to different questions. The "
             f"gap is {stale} routes that were declared after a hint run for an *earlier* "
             "task in the same session, which counts as compliance session-wide and as a "
             "miss per route. Denominator is the anchor-attributed subset, effectively all "
             "July-August 2026: pre-July transcripts are pruned, so pre-July routes are "
             "excluded as not measurable rather than counted as misses."))
    out.append(metric(
        "hint_could_inform_route", "measured",
        "did a `cortex hint` run early enough that its output could have changed the route?",
        informed, total,
        excluded={"routes with no transcript join": unattributed},
        note="Strictly stronger than hint_before_route: it removes hints issued inside "
             "the same shell command as the `log-line` that declared the route, where the "
             "routing line was already composed before the hint printed anything. This is "
             "the number to read if the question is whether the advisory step did any work."))

    hinted = [r for r in attributed if r["hint"]["ran"]]
    on_task = sum(1 for r in hinted if r["hint"]["query_matched"] in ("exact", "overlap"))
    out.append(metric(
        "hint_query_matched_task", "measured",
        "when hint ran, was it asked about this route's own task?",
        on_task, len(hinted),
        detail={"exact": sum(1 for r in hinted if r["hint"]["query_matched"] == "exact"),
                "overlap": sum(1 for r in hinted if r["hint"]["query_matched"] == "overlap"),
                "unrelated": sum(1 for r in hinted if r["hint"]["query_matched"] == "unrelated"),
                "overlap_threshold": QUERY_OVERLAP},
        note=f"Uses a {QUERY_OVERLAP:.0%} token-overlap threshold, which is a knob. Read "
             "it as a refinement of hint_before_route, not as a replacement — the "
             "unthresholded parent is the number to gate on if either is ever gated. "
             "Hand-checked: the `unrelated` bucket is mostly paraphrase, so this "
             "understates."))

    classes = Counter(r["outcome_provenance"] for r in attributed)
    with_outcome = total - classes["none"]
    lags = sorted(r["outcome_cmd_lag_min"] for r in attributed
                  if r["outcome_provenance"] == "observation"
                  and r["outcome_cmd_lag_min"] is not None)
    out.append(metric(
        "outcome_is_observation", "measured",
        "of routes carrying an outcome, how many show no evidence the label was ceremony?",
        classes["observation"], with_outcome,
        excluded={"routes with no outcome recorded": classes["none"],
                  "routes with no transcript join": unattributed},
        detail=dict(classes, observation_with_outcome_command_in_window=len(lags),
                    observation_lag_min_median=(lags[len(lags) // 2] if lags else None),
                    observation_lag_min_max=(lags[-1] if lags else None)),
        note="`observation` is an absence-of-evidence class, not a verified one. The two "
             "ceremony tests (outcome stamped within 90s of the route's own declaration; "
             "outcome batched into the next route's declaration command) are borrowed "
             "from derive_outcomes, where they hand-checked 10/10 and 5/5 correct. They "
             "have good precision and unknown recall, so the true observation rate is at "
             "or below this figure. Supporting context, not proof: of the routes in the "
             f"`observation` class, {len(lags)} have a `cortex outcome` command inside "
             "their own transcript window, at a median lag of "
             f"{(lags[len(lags) // 2] if lags else 0):.0f} minutes from the declaration — "
             "consistent with a verdict rendered after work happened rather than with the "
             "ceremony pattern."))
    return out


# ---------------------------------------------------------------------------
# Session coverage — the banded metric
# ---------------------------------------------------------------------------
def classify_session(session_id, bucket, first_route_ts, routed_sessions):
    """Reduce one transcript session to the facts the coverage band needs."""
    events = bucket["events"]
    files = bucket["files"]
    project = files[0].parent.name if files else "?"
    user_turns = [e for e in events if e.kind == "user"
                  and not any(m in e.text for m in D.INTERRUPT_MARKERS)]
    writes = [e for e in events if e.kind == "tool_use"
              and e.tool in ("Edit", "Write", "NotebookEdit")]
    opening = user_turns[0].text if user_turns else ""

    exclusion = None
    for pattern, reason in AUTOMATION_PREAMBLES:
        if re.search(pattern, opening):
            exclusion = reason
            break
    if exclusion is None:
        for prefix, reason in AUTOMATION_DIRS:
            if project.startswith(prefix):
                exclusion = reason
                break
    if exclusion is None and not user_turns:
        exclusion = "no typed user turn"
    if exclusion is None and events and events[0].ts < first_route_ts:
        exclusion = "predates the first logged route"
    if exclusion is None and opening.startswith("This session is being continued"):
        # A compaction continuation inherits its work from a parent session that this join
        # cannot reach. Its route may well have been declared there. Counting it as a miss
        # would be manufacturing one.
        exclusion = "compaction continuation of an unjoinable parent session"

    return {
        "session": session_id,
        "project": project,
        "start": iso(events[0].ts) if events else None,
        "user_turns": len(user_turns),
        "file_writes": len(writes),
        "events": len(events),
        "routed": session_id in routed_sessions,
        "excluded": exclusion,
        "opening": opening[:120].replace("\n", " "),
    }


def coverage_band(session_records):
    """The banded coverage metric, as a ladder of substantiveness thresholds."""
    eligible = [s for s in session_records if not s["excluded"]]
    excluded = Counter(s["excluded"] for s in session_records if s["excluded"])

    rungs = []
    for min_turns, min_writes, label in SUBSTANTIVE_LADDER:
        pool = [s for s in eligible
                if s["user_turns"] >= min_turns and s["file_writes"] >= min_writes]
        routed = sum(1 for s in pool if s["routed"])
        rungs.append({"min_user_turns": min_turns, "min_file_writes": min_writes,
                      "label": label, "numerator": routed, "denominator": len(pool),
                      "value": ratio(routed, len(pool))})

    low = min((r for r in rungs if r["denominator"]), key=lambda r: r["value"], default=None)
    high = max((r for r in rungs if r["denominator"]), key=lambda r: r["value"], default=None)

    return metric(
        "session_routed", "banded",
        "did sessions where the protocol should have applied actually log a route?",
        excluded=dict(excluded),
        band={
            "low": low, "high": high,
            "ladder": rungs,
            "breaks_the_low_end": "assumes every eligible session needed a route. The "
                                  "Skip protocol says otherwise, so the low end is a "
                                  "floor and is certainly too pessimistic.",
            "breaks_the_high_end": "assumes any session with sustained turns and several "
                                   "file writes needed a route. A long session of "
                                   "individually trivial edits would break this, so the "
                                   "high end can itself be exceeded by the truth.",
        },
        detail={"eligible_sessions": len(eligible),
                "routed_eligible_sessions": sum(1 for s in eligible if s["routed"]),
                "total_sessions_seen": len(session_records)},
        note="NOT a single figure and must not be quoted as one. Every rung is a measured "
             "ratio; the choice of rung is a judgement about where trivial ends, and "
             "nothing in the artifacts records that judgement. Transcript pruning also "
             "means this is a July-August picture: sessions before then largely no longer "
             "exist to be counted, in either the numerator or the denominator.")


# ---------------------------------------------------------------------------
# Observations that are counts, not rates
# ---------------------------------------------------------------------------
def ghost_declarations(sessions, anchor_index, rows):
    """Declaration commands whose task matches no row in the log.

    Reported as a count with evidence, never as a rate: the denominator would have to be
    "declarations attempted", which is only observable through the same transcripts that
    produced the numerator. Two readings fit the evidence — the write failed silently, or
    the task string that landed differs from the one in the command — and this file does
    not choose between them.
    """
    known = {r.get("task_hash") for r in rows}
    out = []
    for digest, hits in anchor_index.items():
        if digest in known:
            continue
        for session_id, ts, command in hits:
            if TEST_HARNESS_RE.search(command):
                continue
            index = re.search(r"cortex\s+log(-line)?\s+", command)
            out.append({"session": session_id, "ts": iso(ts), "task_hash": digest,
                        "evidence": D.excerpt(command, index, radius=160)})
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def dropped_metrics():
    """Metrics considered and not shipped. Present in the output on purpose.

    A scorer that silently omits what it could not measure looks more complete than it is,
    which is the exact failure this whole exercise is meant to remove.
    """
    return [
        metric("route_line_shown_to_user", "dropped",
               "was the routing line declared to Amit before execution?",
               note="Two independent reasons. The log's own `shown_inline` field exists on "
                    "32 rows and is false on all 32, so it records nothing. And detecting "
                    "the declaration in the transcript needs assistant prose, which the "
                    "shared transcript reader deliberately does not emit — adding a second "
                    "reader to get at it would create exactly the divergence this file "
                    "avoids by importing derive_outcomes. Matching a routing line inside "
                    "prose is also fuzzy in a way the other metrics here are not."),
        metric("tier_calibrated", "dropped",
               "was the tier the right tier?",
               note="Not a conformance question. `tier_reason` is free text and always "
                    "present, so a field check would score 100% and mean nothing. Judging "
                    "the tier itself needs a human; `cortex audit-tiers` is the tool for "
                    "that and 10 rows already carry a `tier_audit_original` reclassification."),
        metric("class_correct", "dropped",
               "was the task classified into the right class?",
               note="There is no ground truth for class. Any automatic check would be this "
                    "file inventing labels and then grading against them."),
        metric("skip_was_legitimate", "dropped",
               "when a session did not route, was skipping correct?",
               note="The decision to skip leaves no artifact. This is the missing piece "
                    "that forces session_routed to be banded rather than scored, and no "
                    "amount of transcript reading recovers it. Recording an explicit skip "
                    "would make it measurable; nothing today does."),
    ]


def build(rows, sessions, anchor_index, anchor_times):
    records = []
    for row in rows:
        attribution = D.attribute(row, anchor_index, anchor_times, sessions)
        hint = hint_check(row, attribution, sessions, anchor_times)
        provenance, findings, lag = ("none", [], None)
        if hint is not None:
            provenance, findings = outcome_provenance(row, sessions, attribution)
            lag = outcome_command_lag(sessions, attribution)
        records.append({
            "schema": SCHEMA_VERSION,
            "kind": "route",
            "task_hash": row.get("task_hash"),
            "route_ts": row.get("ts"),
            "project": row.get("project"),
            "class": row.get("class"),
            "tier": row.get("tier"),
            "agent": row.get("agent"),
            "system": row.get("system"),
            "task": (row.get("task") or "")[:160],
            "attribution_method": attribution.get("method"),
            "session": attribution.get("session"),
            "hint": hint,
            "outcome": row.get("outcome"),
            "outcome_backfilled": bool(row.get("outcome_backfilled")),
            "outcome_provenance": provenance,
            "outcome_cmd_lag_min": lag,
            "outcome_provenance_evidence": [
                {"signal": f["signal"], "detail": f["detail"], "evidence": f["evidence"][:240]}
                for f in findings],
        })

    routed_sessions = set()
    for hits in anchor_index.values():
        for session_id, _, command in hits:
            if not TEST_HARNESS_RE.search(command):
                routed_sessions.add(session_id)

    first_route = min((D.parse_ts(r.get("ts")) for r in rows if r.get("ts")),
                      default=datetime.now(timezone.utc))
    session_records = [classify_session(sid, bucket, first_route, routed_sessions)
                       for sid, bucket in sessions.items()]
    session_records.sort(key=lambda s: (s["start"] or ""))

    metrics = log_metrics(rows)
    metrics += transcript_metrics(records)
    metrics.append(coverage_band(session_records))
    metrics += dropped_metrics()

    coverage = Counter()
    for row, record in zip(rows, records):
        month = (row.get("ts") or "")[:7]
        coverage[month, bool(record["hint"] is not None)] += 1
    by_month = {}
    for (month, joined), count in coverage.items():
        entry = by_month.setdefault(month, {"rows": 0, "attributed": 0})
        entry["rows"] += count
        if joined:
            entry["attributed"] += count
    for entry in by_month.values():
        entry["attributed_pct"] = ratio(entry["attributed"], entry["rows"])

    return records, session_records, metrics, by_month


def check_floors(metrics, thresholds_path):
    """Enforce the adherence floors. Returns the number of breaches.

    Floors catch regression. They are deliberately set below where the system sits, so a
    breach means something changed rather than that the current state is good — the
    targets in the same file are what good would look like. A metric that cannot be
    measured in this run is reported as such and never counted as a pass.
    """
    spec = json.loads(Path(thresholds_path).read_text())
    by_id = {m["id"]: m for m in metrics}
    breaches, checked = [], 0
    print("\nADHERENCE GATE")
    for mid, rule in spec.get("floors", {}).items():
        m = by_id.get(mid)
        if not m or m.get("value") is None:
            print(f"  {mid:26s}    n/a  not measurable this run — NOT counted as a pass")
            continue
        checked += 1
        ok = m["value"] >= rule["min"]
        if not ok:
            breaches.append(mid)
        print(f"  {mid:26s} {m['value']:6.1%}  floor {rule['min']:.0%}   "
              f"{'ok' if ok else 'BREACH'}")
    for mid, rule in spec.get("targets", {}).items():
        m = by_id.get(mid)
        if m and m.get("value") is not None:
            gap = rule["goal"] - m["value"]
            print(f"  {mid:26s} {m['value']:6.1%}  target {rule['goal']:.0%}   "
                  f"{'met' if gap <= 0 else f'{gap:+.0%} to go'}")
    print(f"\n{checked} floor(s) checked, {len(breaches)} breached")
    return len(breaches)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--log", default=str(LOG_PATH), help="cortex log to read (never written)")
    parser.add_argument("--projects", default=str(PROJECTS_DIR), help="transcript root")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output JSONL")
    parser.add_argument("--summary", action="store_true", help="print a summary to stdout")
    parser.add_argument("--dry-run", action="store_true", help="score but write nothing")
    parser.add_argument("--check", action="store_true",
                        help="enforce the floors in adherence-thresholds.json and exit "
                             "non-zero if any is breached. Floors detect regression; they "
                             "do not certify the current state as acceptable")
    parser.add_argument("--thresholds",
                        default=str(Path(__file__).resolve().parent / "adherence-thresholds.json"))
    parser.add_argument("--show", metavar="METRIC",
                        help="print the per-route classification behind one metric, with "
                             "evidence, for hand-checking. One of: hint_before_route, "
                             "hint_could_inform_route, outcome_is_observation, session_routed")
    args = parser.parse_args(argv)

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"no log at {log_path}", file=sys.stderr)
        return 1
    raw = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw.append(json.loads(line))
        except ValueError:
            continue
    rows = [r for r in raw if is_route(r)]
    non_route_rows = len(raw) - len(rows)

    sessions = D.load_sessions(Path(args.projects))
    anchor_index, anchor_times = D.build_anchor_index(sessions)
    records, session_records, metrics, by_month = build(rows, sessions, anchor_index, anchor_times)
    ghosts = ghost_declarations(sessions, anchor_index, rows)

    header = {
        "schema": SCHEMA_VERSION,
        "kind": "header",
        "generated_at": iso(datetime.now(timezone.utc)),
        "log": str(log_path),
        "log_rows": len(rows),
        "non_route_rows_excluded": non_route_rows,
        "transcript_sessions": len(sessions),
        "attribution_by_month": by_month,
        "metrics": metrics,
        "ghost_declarations": ghosts,
        "warning": "Adherence to protocol steps only. Says nothing about whether routing "
                   "was correct or whether the work succeeded. `measured` metrics have "
                   "named denominators; `banded` metrics do not have a single value and "
                   "must not be quoted as one; `dropped` metrics are listed with the "
                   "reason they are absent. Transcript-derived metrics cover July-August "
                   "2026 only, because earlier transcripts have been pruned.",
    }

    if not args.dry_run:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as handle:
            handle.write(json.dumps(header) + "\n")
            for record in records:
                handle.write(json.dumps(record) + "\n")
            for record in session_records:
                handle.write(json.dumps(dict(record, schema=SCHEMA_VERSION,
                                             kind="session")) + "\n")
        print(f"wrote {len(records)} route records and {len(session_records)} session "
              f"records to {out_path}")

    if args.show:
        show(args.show, records, session_records)

    if args.summary or args.dry_run:
        summarise(metrics, by_month, ghosts, len(rows), len(sessions), non_route_rows)
    if args.check:
        breaches = check_floors(metrics, args.thresholds)
        if breaches:
            return 1
    return 0


def show(name, records, session_records):
    if name == "session_routed":
        for entry in session_records:
            if entry["excluded"]:
                continue
            flag = "ROUTED  " if entry["routed"] else "no route"
            print(f"{flag} turns={entry['user_turns']:3d} writes={entry['file_writes']:3d} "
                  f"{entry['start']}  {entry['project'][:38]:38s} {entry['opening'][:70]!r}")
        return
    for record in records:
        if name in ("hint_before_route", "hint_could_inform_route"):
            hint = record["hint"]
            if hint is None:
                continue
            if name == "hint_before_route":
                verdict = "HINT" if hint["ran"] else "none"
            else:
                verdict = "HINT" if hint["could_inform"] else (
                    "same-cmd" if hint["ran"] else "none")
            print(f"\n{verdict:9s} {record['route_ts']}  {record['task_hash']}  "
                  f"[{record['class']}/{record['tier']}]")
            print(f"  task:    {record['task'][:100]}")
            print(f"  session: {record['session']}  window from {hint['window_start']}")
            if hint["ran"]:
                print(f"  match:   {hint['query_matched']}  at {hint['hint_ts']}")
                print(f"  cmd:     {hint['evidence'][:220]!r}")
        elif name == "outcome_is_observation":
            if record["hint"] is None or not record["outcome"]:
                continue
            print(f"\n{record['outcome_provenance']:12s} {record['route_ts']}  "
                  f"{record['task_hash']}  outcome={record['outcome']}")
            print(f"  task: {record['task'][:100]}")
            for evidence in record["outcome_provenance_evidence"]:
                print(f"  {evidence['signal']}: {evidence['detail']}")
                print(f"    {evidence['evidence'][:200]!r}")


def summarise(metrics, by_month, ghosts, rows, sessions, non_route_rows=0):
    print(f"\nroute rows          {rows}"
          + (f"  ({non_route_rows} non-route event row(s) excluded)" if non_route_rows else ""))
    print(f"transcript sessions {sessions}")
    print("\ntranscript join coverage by month (governs every transcript-derived metric)")
    for month in sorted(by_month):
        entry = by_month[month]
        print(f"  {month}  rows={entry['rows']:3d}  attributed={entry['attributed']:3d}  "
              f"({entry['attributed_pct']:.0%})")

    print("\nMEASURED — numerator/denominator both named, no circularity")
    for m in metrics:
        if m["status"] != "measured":
            continue
        # An empty denominator prints as n/a rather than crashing or, worse, as 0%.
        # "no data" and "never done" are different findings and must not be conflated.
        value = f"{m['value']:6.1%}" if m["value"] is not None else "   n/a"
        print(f"  {m['id']:26s} {m['numerator']:4d}/{m['denominator']:<4d} "
              f"{value}   {m['question']}")
        if m["excluded"]:
            for reason, count in m["excluded"].items():
                print(f"  {'':26s}      excluded {count}: {reason}")
        if m["id"] == "agent_field_populated":
            alt = m["detail"]["excluding_direct"]
            if alt["value"] is not None:
                print(f"  {'':26s}      excluding Direct rows: {alt['numerator']}/"
                      f"{alt['denominator']} = {alt['value']:.1%}")
            print(f"  {'':26s}      at least {m['detail']['agent_named_in_pattern_instead']}"
                  f" more name an agent inside `pattern` (parser fold-in), so this "
                  f"understates")
        if m["id"] == "hint_before_route":
            alt = m["detail"]["session_level_reading"]
            if alt["value"] is not None:
                print(f"  {'':26s}      same data read per SESSION: {alt['numerator']}/"
                      f"{alt['denominator']} = {alt['value']:.1%} — the ~2x gap is "
                  f"{m['detail']['routes_with_a_hint_earlier_in_the_session_but_not_their_own']}"
                  f" routes riding an earlier task's hint")

    band = next((m for m in metrics if m["status"] == "banded"), None)
    if band:
        print(f"\nBANDED — denominator is a judgement call, so there is no single number")
        print(f"  {band['id']}: {band['question']}")
        for rung in band["band"]["ladder"]:
            value = f"{rung['value']:6.1%}" if rung["value"] is not None else "   n/a"
            print(f"    >={rung['min_user_turns']} turns, >={rung['min_file_writes']} writes  "
                  f"{rung['numerator']:3d}/{rung['denominator']:<3d} {value}   {rung['label']}")
        low, high = band["band"]["low"], band["band"]["high"]
        if low and high:
            print(f"    BAND {low['value']:.0%} – {high['value']:.0%}")
        print(f"    floor breaks if: {band['band']['breaks_the_low_end']}")
        print(f"    ceiling breaks if: {band['band']['breaks_the_high_end']}")
        print("    excluded from every rung:")
        for reason, count in sorted(band["excluded"].items(), key=lambda x: -x[1]):
            print(f"      {count:3d}  {reason}")

    print("\nDROPPED — considered, not shipped")
    for m in metrics:
        if m["status"] == "dropped":
            print(f"  {m['id']:26s} {m['note'][:150]}")

    if ghosts:
        print(f"\nOBSERVATION — {len(ghosts)} declaration command(s) whose task matches no "
              f"log row (count, not a rate):")
        for ghost in ghosts:
            print(f"  {ghost['ts']}  {ghost['session'][:8]}  {ghost['evidence'][:150]!r}")


if __name__ == "__main__":
    sys.exit(main())
