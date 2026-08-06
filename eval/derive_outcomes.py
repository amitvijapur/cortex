#!/usr/bin/env python3
"""derive_outcomes — passive, evidence-derived signals for logged Cortex routes.

WHAT THIS MEASURES
    Evidence of *failure* around a route, recovered from artifacts that already exist:
    session transcripts under ~/.claude/projects and git history in the repo the route
    ran in. Every signal it emits points at a quotable piece of evidence — a user
    utterance, a shell command, a commit — that a human can go read.

WHAT IT DOES NOT MEASURE
    Success. There is no positive class and there never will be one. The variable this
    replaces defined `shipped` as "the user did not push back", which manufactured a
    positive label out of silence; the whole point of deriving rather than self-reporting
    is to stop doing that. A route with no failure evidence is `unknown`, not good.

    Routing quality. Every signal here is a property of the *session*, confounded by task
    difficulty. A long session with two rework loops may be a correct L4 route working as
    designed. These signals are a triage frame — a way to pick the handful of routes per
    month that deserve a human read — not a verdict.

PRECISION OVER RECALL
    This is the explicit optimisation target, and it is the reason several tempting
    signals are absent. A false "this route failed" is worse than a missed one: the
    failure mode being corrected is the manufacture of confident labels, and manufacturing
    confident *negative* labels is the same bug wearing a different hat. Concretely:

      - The dissatisfaction lexicon is deliberately narrow. It only matches user-typed
        turns, plain-text only, under a length cap, after tool results and pasted
        material are excluded. A loose scan over all user content flags ~60% of sessions
        and is nearly all false positives (measured in the design note, §0.3).
      - Signals that cannot be disambiguated from ordinary work are downgraded, not
        dropped, and carry `confidence: low` so they can be filtered out entirely.
      - Anything that cannot be attributed to a route with direct evidence is reported
        as `unattributed`. It is never guessed at.

    Recall is consequently poor and unmeasured. Routes with no signal are the large
    majority and mean nothing.

HOW A ROUTE IS JOINED TO A TRANSCRIPT
    Two mechanisms, in preference order. Neither is the `session_id` field, which is a
    UTC hour bucket: 81 of the 141 historical rows share a bucket with another row and
    18 buckets span more than one project, so it cannot identify anything.

    1. `session_ref` (exact). bin/cortex now records the host session id, which is the
       name the transcript is filed under. This is the intended path. As of this writing
       *no historical row carries it* — it was added after all 141 rows were written —
       so in practice today it contributes nothing and the code path is untested against
       real data. It is implemented so that new rows join for free.

    2. Anchor-command match (evidence). The row was written by a `cortex log-line` /
       `cortex log` shell command, and that command is preserved verbatim in the
       transcript as a Bash tool_use. Parsing the task string out of the command and
       hashing it with bin/cortex's own `task_hash` recovers the exact row. This is not
       a heuristic: the matched command is the row's own act of creation. It also yields
       an anchor *timestamp*, which is what makes per-route (rather than per-session)
       windows possible in sessions that declared several routes.

    A match is only accepted when it is unique, or when the anchor timestamp agrees with
    the row's own `ts` to within ANCHOR_TS_TOLERANCE. Ambiguous matches are discarded
    rather than resolved by preference. Rows that match neither way are emitted with
    `attribution: none` and no signals at all.

WINDOW
    From the anchor command to the next route anchor in the same session, or to the last
    event in the session when it is the final route, cut short at the first inactivity gap
    over WINDOW_MAX_GAP. Evidence outside that window is not attributed to the route.
    Sessions reached only via `session_ref` with no anchor command get the whole session,
    flagged `window_kind: session`.

WHAT IT FOUND, 2026-08-05, over 141 rows and 181 transcript sessions
    Attribution: 80 rows (57%) joined by anchor command, 7 ambiguous, 54 unjoinable.
    Zero rows joined by `session_ref` because no row carries one yet.

    Route-level findings, with precision hand-checked against the transcripts:

      outcome_batched_with_next_route   10 routes   10/10 correct
      outcome_stamped_at_declaration     5 routes    5/5 correct
      delivery_gap_reported              4 routes    5/5 correct
      rework_loop                       10 routes   mechanically true, no shown meaning
      user_interrupt                    14 routes   mechanically true, no shown meaning
      declared_no_work                   1 route     0/1 correct
      user_dissatisfaction               0 routes

    `derived_state` is `unknown` for all 141 rows. Not one route carries high-confidence
    failure evidence inside its own window.

    The two unambiguous dissatisfaction utterances in the corpus — the ones the design
    note found — are both real and both land *outside* every attributable window: one
    2h44m after the last route of its session, one a day before its session's first
    route. They are emitted as `orphan_evidence`, unattached. This is the headline result
    and it is a negative one: the signal with the most meaning is the one this join cannot
    reach.

    The label-provenance signals are the only ones that both fire and mean something
    today. 15 of 80 attributed routes (19%) have direct evidence that their recorded
    `outcome` was ceremony rather than observation, which reproduces the design note's
    §0.2 finding from a different direction.

READ-ONLY
    Reads the cortex log, the transcripts, and `git log` / `git show` in the repos routes
    ran in. Writes exactly one file, under the state dir, keyed by task_hash and
    session so it can be joined back to routes later. It never writes to the cortex log
    and never touches a transcript.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLAUDE_DIR = Path(os.environ.get("CORTEX_HOME") or Path.home() / ".claude")
LOG_PATH = CLAUDE_DIR / "cortex-log.jsonl"
PROJECTS_DIR = CLAUDE_DIR / "projects"
DEFAULT_OUT = REPO / ".omc" / "state" / "derived-outcomes" / "derived_outcomes.jsonl"

SCHEMA_VERSION = "derived-v1"

# A row is written by its anchor command, so their timestamps should be seconds apart.
# The tolerance is generous because the transcript records when the tool call was issued
# and the log records when the process wrote, and a compound shell command can put
# minutes between the two.
ANCHOR_TS_TOLERANCE = timedelta(minutes=20)

# User turns longer than this are pasted material, specs, or dictated context rather than
# a reaction. The dissatisfaction signal is about reactions.
MAX_REACTION_CHARS = 320

# A route's window closes at the next route, or at the first stretch of inactivity longer
# than this. Without the gap cut a session resumed three days later hands the last route
# an 80-hour window and every event in the resumed stretch, which is attribution by
# accident. The cut costs recall on genuinely long-running routes and is taken anyway:
# evidence attributed to the wrong route is the failure this file is built to avoid.
WINDOW_MAX_GAP = timedelta(hours=3)

# An outcome stamped this soon after its own route was declared cannot have observed the
# route. Kept short so the finding stays unarguable.
DECLARATION_WINDOW = timedelta(seconds=90)


# ---------------------------------------------------------------------------
# Dissatisfaction lexicon
#
# Each pattern was written to have a low false-positive rate on *user-typed, short,
# plain-text* turns specifically, which is a far narrower input than "user content".
# Patterns are grouped by how much they can carry on their own:
#
#   strong — the utterance is an explicit rejection or an order to undo. Little else
#            produces these words in a short reaction turn.
#   weak   — genuinely ambiguous. "go back" is sometimes navigation, "not what I asked"
#            is sometimes about a third party's code. These fire at confidence `low`
#            and are intended to be filtered out by default.
#
# Deliberately excluded: bare "no", "wrong", "fix", "instead", "switch to", "actually".
# All of them are common in ordinary instruction-giving and each one alone destroys
# precision. "switch to" in particular appears constantly inside pasted documentation.
# ---------------------------------------------------------------------------
STRONG_DISSATISFACTION = [
    (r"\brevert (it|that|this|these|those|the (change|changes|commit|edit|edits))\b", "explicit revert order"),
    (r"\bundo (it|that|this|all of (that|this)|the (change|changes|last))\b", "explicit undo order"),
    (r"\b(that|this|it)('| i)?s (not right|wrong|broken|garbage|useless|terrible|awful)\b", "explicit rejection"),
    (r"\blooks like (shit|crap|garbage)\b", "explicit rejection"),
    (r"\b(you|u) (broke|ruined|messed up|fucked up)\b", "attributed breakage"),
    (r"\bwhat the (fuck|hell) (happened|did you|are you)\b", "explicit rejection"),
    (r"\b(that|this) (didn'?t|does ?n'?t) work\b", "reported non-function"),
    (r"\bstill (broken|failing|not working|doesn'?t work)\b", "reported non-function after a fix"),
    (r"\bnot what (i|I) (asked|wanted|said)\b", "spec miss"),
    (r"\bwrong approach\b", "route rejection"),
    (r"\bstop\b.{0,20}\b(doing|that|this)\b.{0,30}\b(wrong|not|no)\b", "halt order"),
    (r"\b(that|this|it)'?s not working\b", "reported non-function"),
]

# A distinct, milder class: the user reports that something said to be delivered is not
# there. Kept separate from the strong lexicon and held at `medium` because the user
# looking in the wrong place produces the same words as a real delivery gap. Hand-checked
# over the corpus: 11 matches, 10 of which are genuine "you said it is done, it is not
# there" reports.
DELIVERY_GAP = [
    (r"\b(i )?(don'?t|dont|cant|can'?t|couldn'?t) (see|find) (the|it|that|any)\b",
     "user reports a delivered item is not present"),
    (r"\b(isn'?t|is not) (showing|there|appearing)\b",
     "user reports a delivered item is not present"),
    (r"\bnothing (happened|showed|changed)\b", "user reports no visible effect"),
]

WEAK_DISSATISFACTION = [
    (r"\bgo back to\b", "possible revert request"),
    (r"\bwhy (did|are) you\b", "challenge to the model's choice"),
    (r"\bi (told|said) (you|u)\b", "repeated instruction"),
    (r"\bagain\b.{0,25}\b(broke|fail|wrong|error)\b", "repetition complaint"),
    (r"\bthat'?s not (it|what)\b", "spec miss"),
]
# Removed after hand-checking: `why did we`. It fired on four turns in the corpus, three
# of which were domain questions about the user's own business ("why did we buy it") with
# "we" meaning his company, not the model. The fourth was already caught by the strong
# lexicon. A pattern whose only unique hits are false positives is worth less than the
# recall it buys. `why did you` is kept: it is aimed at the model and fires on nothing
# today, which costs nothing.

# Shell commands that discard work, with the confidence each one can carry alone.
#
# Only `git revert` is high: it undoes work that had already landed as a commit, and
# nothing else produces it. The working-tree commands are demoted to medium after a
# hand-check found the single `git reset --hard` in the corpus was cleanup inside a
# merge-conflict probe, not discarded work. That is the general case — reset, checkout
# and restore are ordinary scratch hygiene, and treating them as failure evidence buys
# recall at exactly the cost this file refuses to pay.
REVERT_COMMANDS = [
    (r"\bgit\s+revert\b", "git revert", "high"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard", "medium"),
    (r"\bgit\s+checkout\s+(--|HEAD\b|\.\s*$)", "git checkout discard", "medium"),
    (r"\bgit\s+restore\s+(?!--staged)", "git restore", "medium"),
    (r"\bgit\s+stash\s+drop\b", "git stash drop", "medium"),
]

# Scripts that probe rather than change. A reset inside one of these is the probe cleaning
# up after itself.
PROBE_MARKERS = (r"merge\s+--no-commit", r"--dry-run", r"\bgit\s+merge-tree\b")

# Shell commands that change something. Used only to establish that a route produced
# *some* artifact, so it is deliberately broad — a false "work happened" costs recall on
# one signal, a false "nothing happened" is a manufactured failure label.
MUTATION_RE = re.compile(
    r"\bgit\s+(commit|push|merge|rebase|cherry-pick|tag|am|apply)\b"
    r"|\bgh\s+(pr|release|issue|repo)\s+(create|merge|edit|close|comment|upload)"
    r"|\b(mv|cp|mkdir|touch|install|ln)\s"
    r"|>\s*\S+\.(py|md|json|ts|tsx|js|yml|yaml|toml|txt|sh|html|css)\b"
    r"|<<\s*['\"]?(PY|EOF|SH|MD|JSON)\b"
    r"|\bnpm\s+(publish|install)\b|\bpip\s+install\b|\buv\s+(add|pip)\b")

INTERRUPT_MARKERS = ("[Request interrupted by user]",
                     "[Request interrupted by user for tool use]")

# Signals that describe the recorded label rather than the route. They are reported but
# never allowed to classify a route as failed.
LABEL_SIGNALS = {"outcome_batched_with_next_route", "outcome_stamped_at_declaration"}


# ---------------------------------------------------------------------------
# Helpers shared with bin/cortex. Reimplemented rather than imported because importing
# bin/cortex executes its module body, and this script must not touch cortex state.
# The one function that matters is task_hash, which is four lines and pinned by a test
# in this file's __main__ self-check.
# ---------------------------------------------------------------------------
def task_hash(task):
    normalized = " ".join(task.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def parse_ts(value):
    """Parse the two timestamp shapes in play: log rows and transcript events."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


# ---------------------------------------------------------------------------
# Transcript reading
# ---------------------------------------------------------------------------
class Event:
    """One transcript line, reduced to what the signals need."""
    __slots__ = ("ts", "kind", "text", "tool", "cmd", "path", "uuid", "cwd", "session")

    def __init__(self, ts, kind, session, uuid, cwd,
                 text="", tool=None, cmd=None, path=None):
        self.ts = ts
        self.kind = kind          # "user" | "assistant_text" | "tool_use"
        self.session = session
        self.uuid = uuid
        self.cwd = cwd
        self.text = text
        self.tool = tool
        self.cmd = cmd
        self.path = path


def user_text(message):
    """Extract user-typed text, or None when the turn is not a typed message.

    The filters here carry most of the precision. Tool results are the bulk of `user`
    rows and are model-facing, not user-typed. Meta and sidechain rows are harness
    plumbing and subagent traffic. Anything opening with `<` is a wrapper the harness
    injected (local-command output, system reminders, channel envelopes) and its content
    is not something the user chose to say.
    """
    content = message.get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        text = " ".join(parts)
    elif isinstance(content, str):
        text = content
    else:
        return None
    text = text.strip()
    if not text or text.startswith("<"):
        return None
    return text


def read_transcript(path):
    """Yield Events for one transcript file. Malformed lines are skipped silently:
    transcripts are appended live and a truncated final line is normal."""
    try:
        handle = path.open(errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            kind = row.get("type")
            if kind not in ("user", "assistant"):
                continue
            if row.get("isMeta") or row.get("isSidechain"):
                continue
            ts = parse_ts(row.get("timestamp"))
            if ts is None:
                continue
            session = row.get("sessionId")
            uuid = row.get("uuid")
            cwd = row.get("cwd")
            message = row.get("message") or {}
            if kind == "user":
                text = user_text(message)
                if text is None:
                    continue
                yield Event(ts, "user", session, uuid, cwd, text=text)
                continue
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    inp = block.get("input") or {}
                    yield Event(ts, "tool_use", session, uuid, cwd,
                                tool=block.get("name"),
                                cmd=inp.get("command") if isinstance(inp.get("command"), str) else None,
                                path=inp.get("file_path") if isinstance(inp.get("file_path"), str) else None)


def load_sessions(projects_dir):
    """Return {session_id: {"events": [...], "files": [...]}}, events time-sorted.

    Keyed by sessionId rather than by file because one session can span more than one
    file (resume, teleport) and the route window has to follow the session, not the file.
    """
    sessions = defaultdict(lambda: {"events": [], "files": [], "_seen": set()})
    if not projects_dir.is_dir():
        return {}
    for path in sorted(projects_dir.glob("*/*.jsonl")):
        seen = set()
        for event in read_transcript(path):
            if not event.session:
                continue
            bucket = sessions[event.session]
            # The same session can appear in more than one file (resume, teleport, a
            # copied project dir). Deduplicating on the event uuid stops one utterance
            # being counted as two pieces of evidence.
            key = (event.uuid, event.kind, event.tool, event.text[:64], event.cmd)
            if key in bucket["_seen"]:
                continue
            bucket["_seen"].add(key)
            bucket["events"].append(event)
            if path not in seen:
                seen.add(path)
                bucket["files"].append(path)
    for bucket in sessions.values():
        bucket["events"].sort(key=lambda e: e.ts)
        del bucket["_seen"]
    return dict(sessions)


# ---------------------------------------------------------------------------
# Anchors: the `cortex log` commands that created the rows
# ---------------------------------------------------------------------------
LOG_LINE_RE = re.compile(r"cortex\s+log-line\s+")
LOG_RE = re.compile(r"cortex\s+log\s+")
OUTCOME_RE = re.compile(r"cortex\s+outcome\s+(shipped|abandoned|partial|corrected)\b")


def anchor_tasks(command):
    """Extract every task string a `cortex log` command in this shell string declares.

    Shell parsing is done with shlex so that quoting is handled the way the shell handled
    it. A command that shlex cannot parse (unbalanced quotes from a truncated transcript)
    contributes nothing rather than a guess.
    """
    tasks = []
    for match in LOG_LINE_RE.finditer(command):
        parts = split_args(command[match.end():])
        # log-line takes: <routing line> <task> [flags...]
        if len(parts) >= 2 and not parts[1].startswith("-"):
            tasks.append(parts[1])
    for match in LOG_RE.finditer(command):
        tail = command[match.end():]
        flag = re.search(r"--task\s+", tail)
        if not flag:
            continue
        parts = split_args(tail[flag.end():])
        if parts and not parts[0].startswith("-"):
            tasks.append(parts[0])
    return tasks


def split_args(text):
    """shlex.split, with the shell's line-continuation handling put back.

    These commands are written across several lines with trailing backslashes. shlex
    emits the backslash-newline as its own token, which shifts every positional argument
    by one and silently turns the routing line into the task. That bug cost roughly a
    quarter of the achievable join rate before it was found, so the normalisation happens
    here, once, rather than at each call site.
    """
    normalized = re.sub(r"\\\r?\n\s*", " ", text)
    try:
        parts = shlex.split(normalized)
    except ValueError:
        return []
    return [p for p in parts if p.strip()]


def build_anchor_index(sessions):
    """{task_hash: [(session_id, ts, command)]} for every route-creating command found."""
    index = defaultdict(list)
    per_session = defaultdict(list)
    for session_id, bucket in sessions.items():
        for event in bucket["events"]:
            if event.kind != "tool_use" or not event.cmd or "cortex log" not in event.cmd:
                continue
            for task in anchor_tasks(event.cmd):
                digest = task_hash(task)
                index[digest].append((session_id, event.ts, event.cmd))
                per_session[session_id].append(event.ts)
    for stamps in per_session.values():
        stamps.sort()
    return dict(index), dict(per_session)


def truncate_at_gap(events, start, hard_end):
    """Close a window at the first inactivity gap longer than WINDOW_MAX_GAP.

    Returns (end, window_kind). A window that runs to the end of a session which was
    resumed days later would otherwise sweep in unrelated work and attribute it to this
    route.
    """
    end = start
    kind = "route-to-session-end"
    previous = start
    for event in events:
        if event.ts <= start:
            continue
        if event.ts > hard_end:
            break
        if event.ts - previous > WINDOW_MAX_GAP:
            return previous, "route-gap-truncated"
        previous = event.ts
        end = event.ts
    return (hard_end if end == start else end), kind


def attribute(row, anchor_index, anchor_times, sessions):
    """Locate the transcript window for a row. Returns a dict describing the attribution.

    Conservative by construction: an ambiguous anchor match that the timestamp cannot
    disambiguate is reported as ambiguous and carries no window, so no signal can fire
    on it. Nothing here falls back to the hour-bucket `session_id`.
    """
    row_ts = parse_ts(row.get("ts"))
    session_ref = row.get("session_ref")

    candidates = anchor_index.get(row.get("task_hash"), [])
    # Prefer an anchor inside the session the row itself names, when it names one.
    if session_ref:
        scoped = [c for c in candidates if c[0] == session_ref]
        if scoped:
            candidates = scoped

    chosen = None
    method = None
    if len(candidates) == 1:
        chosen = candidates[0]
        method = "anchor-command"
    elif len(candidates) > 1:
        near = [c for c in candidates
                if row_ts and abs(c[1] - row_ts) <= ANCHOR_TS_TOLERANCE]
        if len(near) == 1:
            chosen = near[0]
            method = "anchor-command+ts"
        else:
            return {"method": "ambiguous", "confidence": "none",
                    "session": None, "candidate_sessions": sorted({c[0] for c in candidates}),
                    "note": f"{len(candidates)} anchor commands match this task_hash and "
                            f"{len(near)} of them are within the timestamp tolerance"}

    if chosen is None:
        if session_ref and session_ref in sessions:
            events = sessions[session_ref]["events"]
            return {"method": "session_ref", "confidence": "medium",
                    "session": session_ref,
                    "window_kind": "session",
                    "start": events[0].ts if events else None,
                    "end": events[-1].ts if events else None,
                    "note": "joined on session_ref with no anchor command found; the "
                            "window is the whole session, so signals may belong to a "
                            "different route in it"}
        return {"method": "none", "confidence": "none", "session": None,
                "note": "no anchor command in any transcript and no session_ref; "
                        "this row predates session_ref and its creating command was "
                        "not preserved"}

    session_id, anchor_ts, command = chosen
    later = [t for t in anchor_times.get(session_id, []) if t > anchor_ts]
    events = sessions[session_id]["events"]
    hard_end = later[0] if later else (events[-1].ts if events else anchor_ts)
    end, kind = truncate_at_gap(events, anchor_ts, hard_end)
    if later and end < hard_end:
        kind = "route-gap-truncated"
    elif later:
        kind = "route"
    drift = abs(anchor_ts - row_ts) if row_ts else None
    return {"method": method,
            "confidence": "high" if (drift is not None and drift <= ANCHOR_TS_TOLERANCE) else "medium",
            "session": session_id,
            "window_kind": kind,
            "start": anchor_ts,
            "end": end,
            "anchor_command": command[:400],
            "ts_drift_s": int(drift.total_seconds()) if drift is not None else None}


# ---------------------------------------------------------------------------
# Signals
#
# Every signal returns zero or more findings. A finding is a failure indication with a
# confidence and a verbatim piece of evidence. There is no signal that returns "this went
# well", by design: absence of evidence of failure is not evidence of success, and the
# variable being replaced failed precisely by treating it as such.
# ---------------------------------------------------------------------------
def excerpt(text, match, radius=140):
    """Show the region of a long shell command that actually matched.

    These commands run to thousands of characters and the match is often near the end,
    so a head-truncated excerpt shows evidence that has nothing to do with the finding.
    A reader who cannot see why a signal fired cannot check it, and every signal here is
    supposed to be checkable.
    """
    if match is None:
        return text[:300]
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def finding(name, confidence, evidence, detail=None, ts=None):
    return {"signal": name, "confidence": confidence, "evidence": evidence,
            "detail": detail, "ts": iso(ts)}


def signal_dissatisfaction(window_events):
    """Explicit user dissatisfaction, from short typed reactions only."""
    out = []
    for event in window_events:
        if event.kind != "user":
            continue
        text = event.text
        if len(text) > MAX_REACTION_CHARS:
            continue
        lowered = text.lower()
        # Tiers are tried strongest first and only one finding is emitted per turn, so a
        # turn that is both an explicit rejection and a delivery-gap report is counted
        # once, at the confidence its strongest evidence supports.
        for lexicon, name, confidence in (
                (STRONG_DISSATISFACTION, "user_dissatisfaction", "high"),
                (DELIVERY_GAP, "delivery_gap_reported", "medium"),
                (WEAK_DISSATISFACTION, "user_dissatisfaction_weak", "low")):
            label = first_match(lexicon, lowered)
            if label:
                out.append(finding(name, confidence, text[:MAX_REACTION_CHARS],
                                   label, event.ts))
                break
    return out


def first_match(lexicon, lowered):
    for pattern, label in lexicon:
        if re.search(pattern, lowered):
            return label
    return None


def signal_revert(window_events):
    """Work discarded by a shell command inside the window."""
    out = []
    for event in window_events:
        if event.kind != "tool_use" or not event.cmd:
            continue
        probe = any(re.search(p, event.cmd) for p in PROBE_MARKERS)
        for pattern, label, confidence in REVERT_COMMANDS:
            if not re.search(pattern, event.cmd):
                continue
            if probe and confidence != "high":
                break
            out.append(finding("work_reverted", confidence, event.cmd[:300], label, event.ts))
            break
    return out


def signal_interrupt(window_events):
    """User cut the model off mid-work.

    Low confidence on its own: interruption is also how a user adds a forgotten
    constraint. It is emitted because interruption immediately followed by a corrective
    instruction is a genuine pattern, and separating those two cases needs a reader.
    """
    out = []
    for event in window_events:
        if event.kind != "user":
            continue
        if any(marker in event.text for marker in INTERRUPT_MARKERS):
            out.append(finding("user_interrupt", "low", event.text[:200],
                               "user stopped the model mid-turn", event.ts))
    return out


def signal_rework(window_events):
    """A file written, then written again after the user said something in between.

    The intervening user turn is what separates rework from ordinary iterative editing:
    a model editing the same file five times in a row is working, a model re-editing a
    file after the user speaks is redoing. Still confounded — the user may have asked for
    an unrelated addition to the same file — so this is confidence `low` and reports the
    file and the count so a reader can check.
    """
    edited = {}
    spoke_since = set()
    cycles = Counter()
    for event in window_events:
        if event.kind == "user":
            spoke_since = set(edited)
            continue
        if event.kind != "tool_use" or event.tool not in ("Edit", "Write", "NotebookEdit"):
            continue
        if not event.path:
            continue
        if event.path in spoke_since:
            cycles[event.path] += 1
            spoke_since.discard(event.path)
        edited[event.path] = event.ts
    out = []
    for path, count in cycles.most_common(5):
        if count >= 2:
            out.append(finding("rework_loop", "low", path,
                               f"re-edited after {count} separate user turns"))
    return out


def signal_no_work(row, window_events, window_start, window_end):
    """A build route that produced nothing at all inside its window.

    STATUS: fires on nothing in the current corpus, and that is the corrected behaviour.
    The first version tested only for Edit/Write and `git commit`, fired three times, and
    all three were false positives on hand-check: two windows where the user pivoted
    mid-route to work done entirely through `gh` and `git`, and one ideation route where
    reading and a directory move were the whole job. The artifact test now covers any
    state-mutating shell command, and `design` is excluded because exploration legitimately
    produces no file.

    It is kept rather than deleted because it is the only signal aimed at 2.7's silent
    abandonment mode, and a signal that fires zero times honestly is worth more than one
    that fires three times wrongly.
    """
    if row.get("class") not in ("build", "debug", "quickfix"):
        return []
    if not window_events:
        return []
    wrote = any(e.kind == "tool_use" and e.tool in ("Edit", "Write", "NotebookEdit")
                for e in window_events)
    if wrote:
        return []
    mutated = any(e.kind == "tool_use" and e.cmd and MUTATION_RE.search(e.cmd)
                  for e in window_events)
    if mutated:
        return []
    span = (window_end - window_start).total_seconds() / 60 if window_start and window_end else 0
    return [finding("declared_no_work", "medium",
                    f"{len(window_events)} events over {span:.0f} min, no file writes, no commit",
                    f"class={row.get('class')} route produced no artifact inside its window")]


def signal_repeat_task(row, all_rows):
    """The same task logged again later — the first route did not finish the job.

    Exact task_hash equality only. Near-duplicate matching was considered and rejected:
    a similarity threshold is a knob that trades precision for recall, and this file is
    optimised the other way.
    """
    digest = row.get("task_hash")
    same = [r for r in all_rows if r.get("task_hash") == digest]
    if len(same) < 2:
        return []
    row_ts = parse_ts(row.get("ts"))
    later = [r for r in same
             if parse_ts(r.get("ts")) and row_ts and parse_ts(r.get("ts")) > row_ts]
    if not later:
        return []
    nxt = min(later, key=lambda r: parse_ts(r.get("ts")))
    gap = (parse_ts(nxt["ts"]) - row_ts).total_seconds() / 3600
    return [finding("task_relogged", "medium",
                    f"same task_hash logged again {gap:.1f}h later as "
                    f"{nxt.get('system')} > {nxt.get('pattern')} @ {nxt.get('tier')}",
                    "identical task text routed a second time")]


def signal_label_provenance(row, sessions, attribution):
    """Evidence about the row's existing `outcome` label, not about the route.

    `cortex outcome` closes the latest still-open entry, so the route a given outcome
    command settles is the one whose anchor most recently preceded it. That is what makes
    these two checks attributable at all:

      - `outcome_batched_with_next_route` — the *next* route's declaration command also
        carries a `cortex outcome` call. This route's verdict was the opening move of the
        following route's ceremony, which is a protocol step being cleared rather than a
        result being observed.
      - `outcome_stamped_at_declaration` — an outcome command lands within
        DECLARATION_WINDOW of this route's own declaration. A verdict rendered a minute
        after the route was declared did not observe how the route went.

    These are the highest-precision findings in the file: a string either is or is not
    present in a preserved shell command. They are also the narrowest — they say nothing
    about whether the route was good, only that its recorded label was not an
    observation. Caveat: `cortex outcome` scopes to the current project, so in the rare
    session that routes across two repos the pairing can slip by one route.
    """
    session_id = attribution.get("session")
    start = attribution.get("start")
    end = attribution.get("end")
    if not session_id or session_id not in sessions or start is None:
        return []
    out = []
    anchors_after = []
    for event in sessions[session_id]["events"]:
        if event.kind != "tool_use" or not event.cmd or "cortex" not in event.cmd:
            continue
        declares = bool(LOG_LINE_RE.search(event.cmd) or LOG_RE.search(event.cmd))
        closes = OUTCOME_RE.search(event.cmd)
        if event.ts > start and declares:
            anchors_after.append((event.ts, event.cmd, closes))
        if closes and not declares and start <= event.ts <= (end or event.ts):
            if event.ts - start <= DECLARATION_WINDOW:
                gap = int((event.ts - start).total_seconds())
                out.append(finding("outcome_stamped_at_declaration", "high",
                                   excerpt(event.cmd, closes),
                                   f"verdict and route declaration are {gap}s apart, so "
                                   f"they are one ceremony rather than a declaration and "
                                   f"a later observation", event.ts))
    if anchors_after:
        next_ts, next_cmd, next_closes = min(anchors_after, key=lambda a: a[0])
        if next_closes:
            # `cortex outcome` closes the most recent still-open route for the current
            # project, which at this boundary is normally this one. When this row carries
            # no outcome at all the verdict demonstrably went somewhere else, so the
            # finding is downgraded rather than asserted.
            paired = row.get("outcome") is not None
            out.append(finding(
                "outcome_batched_with_next_route",
                "high" if paired else "medium",
                excerpt(next_cmd, next_closes),
                ("this route's verdict was stamped inside the shell command that declared "
                 "the following route" if paired else
                 "a verdict was stamped inside the command that declared the following "
                 "route, but this row is unmarked, so it settled a different route"),
                next_ts))
    return out


def signal_reverted_commits(repo, window_start, window_end):
    """Commits in the window that a later commit reverted.

    git is consulted read-only. Repos that are missing, are not git, or that error out
    contribute nothing — a missing repo is unknown, not clean.
    """
    if not repo or not window_start or not window_end:
        return []
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "log", "--no-merges",
             f"--since={window_start.isoformat()}",
             f"--until={(window_end + timedelta(hours=6)).isoformat()}",
             "--pretty=%h%x1f%s"],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    out = []
    for line in proc.stdout.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        if subject.lower().startswith("revert"):
            out.append(finding("revert_commit", "high", f"{sha} {subject[:160]}",
                               f"revert commit in {repo}"))
    return out


def window_repo(window_events):
    """The cwd the work happened in, taken from the transcript rather than from the log's
    `project` field, which is a basename and collides across repos."""
    counts = Counter(e.cwd for e in window_events if e.cwd)
    if not counts:
        return None
    path = Path(counts.most_common(1)[0][0])
    return path if (path / ".git").exists() else None


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------
def effort_context(row, window_events, window_start, window_end, baselines):
    """Turn count and elapsed minutes against the median for the route's class.

    Reported as context, never as a finding. Long sessions mean hard tasks at least as
    much as they mean bad routes, and nobody has shown that turn count tracks anything
    Amit cares about. It is here because it is free, has real variance, and is useful for
    ordering a triage queue — not because it means a route was wrong.
    """
    if not window_events:
        return None
    turns = sum(1 for e in window_events if e.kind == "user")
    minutes = (window_end - window_start).total_seconds() / 60 if window_start and window_end else None
    base = baselines.get(row.get("class")) or baselines.get("_all") or {}
    return {"user_turns": turns,
            "elapsed_min": round(minutes, 1) if minutes is not None else None,
            "class_median_turns": base.get("turns"),
            "class_median_min": base.get("minutes"),
            "turns_vs_median": (round(turns / base["turns"], 2)
                                if base.get("turns") else None)}


def compute_baselines(records):
    """Medians per class, computed from the attributed windows themselves.

    Self-referential on purpose: the comparison that matters is a route against other
    routes of its own class in this same log, not against an outside standard that does
    not exist.
    """
    by_class = defaultdict(lambda: {"turns": [], "minutes": []})
    for rec in records:
        ctx = rec.get("effort")
        if not ctx:
            continue
        bucket = by_class[rec["route"]["class"]]
        bucket["turns"].append(ctx["user_turns"])
        if ctx["elapsed_min"] is not None:
            bucket["minutes"].append(ctx["elapsed_min"])
        allb = by_class["_all"]
        allb["turns"].append(ctx["user_turns"])
        if ctx["elapsed_min"] is not None:
            allb["minutes"].append(ctx["elapsed_min"])

    def median(values):
        if not values:
            return None
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return round((ordered[mid - 1] + ordered[mid]) / 2, 1)

    return {name: {"turns": median(b["turns"]), "minutes": median(b["minutes"]),
                   "n": len(b["turns"])}
            for name, b in by_class.items()}


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------
def derive(row, sessions, anchor_index, anchor_times, all_rows, use_git):
    attribution = attribute(row, anchor_index, anchor_times, sessions)
    record = {
        "schema": SCHEMA_VERSION,
        "task_hash": row.get("task_hash"),
        "route_ts": row.get("ts"),
        "route": {"project": row.get("project"), "class": row.get("class"),
                  "system": row.get("system"), "pattern": row.get("pattern"),
                  "tier": row.get("tier"), "task": row.get("task")},
        "self_reported_outcome": row.get("outcome"),
        "attribution": {k: (iso(v) if isinstance(v, datetime) else v)
                        for k, v in attribution.items()},
        "signals": [],
        "effort": None,
        "derived_state": "unknown",
        "derived_state_note": "",
    }

    session_id = attribution.get("session")
    if not session_id:
        record["derived_state_note"] = (
            "unattributed: no transcript window could be established, so no signal "
            "could be evaluated. This says nothing about the route.")
        return record

    start = attribution.get("start")
    end = attribution.get("end")
    events = sessions[session_id]["events"]
    window = [e for e in events
              if (start is None or e.ts >= start) and (end is None or e.ts <= end)]

    findings = []
    findings += signal_dissatisfaction(window)
    findings += signal_revert(window)
    findings += signal_interrupt(window)
    findings += signal_rework(window)
    findings += signal_no_work(row, window, start, end)
    findings += signal_repeat_task(row, all_rows)
    findings += signal_label_provenance(row, sessions, attribution)
    if use_git:
        findings += signal_reverted_commits(window_repo(window), start, end)

    record["signals"] = findings
    record["effort"] = effort_context(row, window, start, end, {})
    record["window_events"] = len(window)

    # `derived_state` has exactly two values. There is no success state and adding one
    # would reintroduce the defect this file exists to remove.
    # The label-provenance signals are evidence about the recorded `outcome`, not about
    # how the route went, so they must not push a route into `failure_evidence`.
    high = [f for f in findings
            if f["confidence"] == "high" and f["signal"] not in LABEL_SIGNALS]
    medium = [f for f in findings if f["confidence"] == "medium"]
    if high:
        record["derived_state"] = "failure_evidence"
        record["derived_state_note"] = (
            f"{len(high)} high-confidence failure signal(s); read the evidence before "
            f"treating this as a failed route")
    elif medium:
        record["derived_state"] = "unknown"
        record["derived_state_note"] = (
            f"{len(medium)} medium-confidence signal(s) only — worth a human read, "
            f"not a label")
    else:
        record["derived_state"] = "unknown"
        record["derived_state_note"] = (
            "no failure evidence found in the window. This is not evidence of success: "
            "recall is poor by design and most failures leave no detectable trace.")
    return record


def orphan_evidence(sessions, anchor_times, records):
    """High-confidence evidence in a routed session that sits outside every attributed
    window.

    This exists because the alternative is worse. The two clearest dissatisfaction
    utterances in the whole corpus both land here: one 2h44m after the last route in its
    session, one a day before the session's first route. Attaching them to the nearest
    route would be manufacturing an attribution, and dropping them would hide the single
    strongest negative signal available. So they are emitted unattached, with the nearest
    preceding route reported as a lead for a human — explicitly not as a join.
    """
    claimed = defaultdict(list)
    for rec in records:
        attribution = rec["attribution"]
        session = attribution.get("session")
        start = parse_ts(attribution.get("start"))
        if session and start:
            claimed[session].append((start, parse_ts(attribution.get("end")) or start))

    out = []
    for session_id, anchors in anchor_times.items():
        if session_id not in sessions:
            continue
        events = sessions[session_id]["events"]
        windows = claimed.get(session_id, [])
        for found in signal_dissatisfaction(events) + signal_revert(events):
            if found["confidence"] != "high":
                continue
            when = parse_ts(found["ts"])
            if when and any(start <= when <= end for start, end in windows):
                continue
            earlier = [a for a in anchors if when and a <= when]
            out.append({
                "schema": SCHEMA_VERSION,
                "kind": "orphan_evidence",
                "session": session_id,
                "signal": found["signal"],
                "confidence": found["confidence"],
                "detail": found["detail"],
                "evidence": found["evidence"],
                "ts": found["ts"],
                "nearest_preceding_route_ts": iso(earlier[-1]) if earlier else None,
                "gap_from_preceding_route_min": (
                    round((when - earlier[-1]).total_seconds() / 60, 1)
                    if earlier and when else None),
                "note": "evidence in a routed session that falls outside every attributed "
                        "route window. NOT attributed to any route — the nearest preceding "
                        "route is a lead for a human, not a join.",
            })
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--log", default=str(LOG_PATH), help="cortex log to read (never written)")
    parser.add_argument("--projects", default=str(PROJECTS_DIR), help="transcript root")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output JSONL")
    parser.add_argument("--no-git", action="store_true", help="skip git history checks")
    parser.add_argument("--summary", action="store_true", help="print a summary to stdout")
    parser.add_argument("--show", metavar="SIGNAL",
                        help="print every finding for one signal name, with evidence")
    parser.add_argument("--dry-run", action="store_true", help="derive but write nothing")
    args = parser.parse_args(argv)

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"no log at {log_path}", file=sys.stderr)
        return 1
    rows = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue

    sessions = load_sessions(Path(args.projects))
    anchor_index, anchor_times = build_anchor_index(sessions)

    records = [derive(r, sessions, anchor_index, anchor_times, rows, not args.no_git)
               for r in rows]

    # Second pass: baselines are computed from the attributed windows, so effort context
    # is filled in only after every window is known.
    baselines = compute_baselines(records)
    for rec, row in zip(records, rows):
        if rec.get("effort"):
            base = baselines.get(rec["route"]["class"]) or {}
            rec["effort"]["class_median_turns"] = base.get("turns")
            rec["effort"]["class_median_min"] = base.get("minutes")
            rec["effort"]["turns_vs_median"] = (
                round(rec["effort"]["user_turns"] / base["turns"], 2)
                if base.get("turns") else None)

    orphans = orphan_evidence(sessions, anchor_times, records)

    if not args.dry_run:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as handle:
            handle.write(json.dumps({
                "schema": SCHEMA_VERSION,
                "kind": "header",
                "generated_at": iso(datetime.now(timezone.utc)),
                "log": str(log_path),
                "log_rows": len(rows),
                "transcript_sessions": len(sessions),
                "orphan_evidence_records": len(orphans),
                "baselines": baselines,
                "warning": "Derived failure evidence only. No positive labels. "
                           "`unknown` means no evidence was found, not that the route "
                           "succeeded. Optimised for precision; recall is poor and "
                           "unmeasured.",
            }) + "\n")
            for rec in records:
                handle.write(json.dumps(rec) + "\n")
            for rec in orphans:
                handle.write(json.dumps(rec) + "\n")
        print(f"wrote {len(records)} route records and {len(orphans)} orphan-evidence "
              f"records to {out_path}")

    if args.show:
        for rec in records:
            for f in rec["signals"]:
                if f["signal"] == args.show:
                    print(f"\n{rec['task_hash']}  {rec['route_ts']}  "
                          f"[{rec['route']['class']}/{rec['route']['tier']}] "
                          f"self={rec['self_reported_outcome']}")
                    print(f"  task: {rec['route']['task'][:110]}")
                    print(f"  session: {rec['attribution'].get('session')}")
                    print(f"  {f['confidence']}: {f['detail']}")
                    print(f"  evidence: {f['evidence'][:240]!r}")

    if args.summary or args.dry_run:
        attributed = [r for r in records if r["attribution"].get("session")]
        methods = Counter(r["attribution"]["method"] for r in records)
        signals = Counter(f["signal"] for r in records for f in r["signals"])
        states = Counter(r["derived_state"] for r in records)
        print(f"\nrows                {len(records)}")
        print(f"transcript sessions {len(sessions)}")
        print(f"attributed          {len(attributed)} "
              f"({100*len(attributed)/max(1,len(records)):.0f}%)")
        print("\nattribution method")
        for name, count in methods.most_common():
            print(f"  {name:22s} {count}")
        print("\nsignals fired (route-count, not finding-count)")
        by_route = Counter()
        for rec in records:
            for name in {f["signal"] for f in rec["signals"]}:
                by_route[name] += 1
        for name, count in by_route.most_common():
            print(f"  {name:34s} {count:3d} routes  ({signals[name]} findings)")
        print("\nderived_state")
        for name, count in states.most_common():
            print(f"  {name:18s} {count}")
        print(f"\norphan evidence (high-confidence, not attributable to a route): {len(orphans)}")
        for rec in orphans:
            print(f"  {rec['ts']}  {rec['signal']}  "
                  f"(+{rec['gap_from_preceding_route_min']}min after last route)  "
                  f"{rec['evidence'][:80]!r}")
        print("\nbaselines (median over attributed windows)")
        # Correction events carry no class, so the key can be None. Sort and format
        # defensively rather than letting a schema addition crash the summary.
        for name, base in sorted(baselines.items(), key=lambda kv: kv[0] or ""):
            label = name or "(no class)"
            print(f"  {label:12s} turns={base['turns']} min={base['minutes']} n={base['n']}")
    return 0


if __name__ == "__main__":
    # Pin task_hash against a known row so a drift in bin/cortex's hashing surfaces here
    # rather than as a silent collapse in the join rate.
    assert task_hash("add graphify to cortex routing") == "34f192d58a86", "task_hash drifted"
    sys.exit(main())
