#!/usr/bin/env python3
"""
PROPOSED — NOT INSTALLED. Read-only probe for runtime subagent invocation.

Answers the question the cortex log cannot: was the agent named in a routing
decision's `agent` field ever actually spawned as a subagent?

Evidence source is the Claude Code runtime itself, not the model. At spawn time
the runtime writes:

    ~/.claude/projects/<project-slug>/<session-uuid>/subagents/
        agent-<agent_id>.jsonl        # the subagent's own transcript
        agent-<agent_id>.meta.json    # {agentType, description, toolUseId,
                                      #  spawnDepth, parentAgentId?, model?}

The .meta.json is written when the agent is SPAWNED and never rewritten, so it
survives agent failure, interruption, and session crash. That is exactly the
property "was the treatment applied" needs.

This script never writes to ~/.claude, never modifies settings, and installs
no hooks. It only reads.

Usage:
    python3 eval/agent_invocation_probe.py                    # summary
    python3 eval/agent_invocation_probe.py --json out.json    # full records
    python3 eval/agent_invocation_probe.py --snapshot dir/    # archive meta files
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
CORTEX_LOG = Path.home() / ".claude" / "cortex-log.jsonl"
AGENTS_DIR = Path.home() / ".claude" / "agents"

# Agent types the runtime provides that have no file in ~/.claude/agents.
BUILTIN_AGENTS = {"general-purpose", "Explore", "Plan", "claude-code-guide",
                  "statusline-setup", "fork"}

# Reconciliation verdicts. The distinction that matters most is
# NO_EVIDENCE vs NOT_INVOKED: absence of a transcript directory is *unknown*,
# not a confirmed negative. Collapsing those two produces confident wrong data.
MATCH = "match"                  # every declared leg was spawned
PARTIAL = "partial"              # some declared legs spawned, others not
SUBSTITUTED = "substituted"      # agents spawned, but none of the declared ones
NOT_INVOKED = "not_invoked"      # session observed, zero depth-1 spawns in window
UNDECLARED = "undeclared"        # agents spawned, route declared none
CONSISTENT_DIRECT = "consistent_direct"   # declared none, spawned none
NO_EVIDENCE = "no_evidence"      # cannot observe: no session dir / pruned / ambiguous

# Declared-agent strings in cortex-log are free text, not a controlled
# vocabulary. Observed separators for fan-outs and pipelines.
LEG_SPLIT = re.compile(r"\s*(?:∥|\|\||\+|→|->|,|/)\s*")
PARENTHETICAL = re.compile(r"\s*\([^)]*\)")

# Strings that appear in the `agent` field but are not agents.
NOT_AN_AGENT = {"amit", "claude", "fable", "direct", "n/a", "none", "-"}

UNRESOLVED = "unresolved_declaration"  # `agent` field holds prose, not agent names


def load_agent_registry() -> set[str]:
    """
    Normalised names of every agent actually installed on this machine.

    This is the authority for deciding whether a declared string is even a
    claim about an agent. Without it, 'Software Architect' (a real agent that
    was not invoked) and 'spread.html' (not an agent at all) both look like
    the same failure, and the second would be miscounted as evidence.
    """
    reg = {norm(a) for a in BUILTIN_AGENTS}
    if not AGENTS_DIR.is_dir():
        return reg
    for md in AGENTS_DIR.rglob("*.md"):
        try:
            with md.open() as fh:
                if fh.readline().strip() != "---":
                    continue
                for _ in range(30):
                    line = fh.readline()
                    if not line or line.strip() == "---":
                        break
                    if line.startswith("name:"):
                        reg.add(norm(line.split(":", 1)[1]))
                        break
        except Exception:
            continue
    return reg


def norm(name: str) -> str:
    """Normalise a declared or observed agent name for comparison."""
    n = PARENTHETICAL.sub("", name or "").strip().lower()
    n = n.split(":")[-1]          # oh-my-claudecode:executor -> executor
    n = re.sub(r"[\s_-]+", " ", n)
    return n.strip()


def declared_legs(agent_field: str, registry: set[str] | None = None):
    """
    Split a free-text `agent` declaration into legs and resolve each against
    the installed registry.

    Returns (resolved, unresolved). `resolved` are legs naming a real installed
    agent and are therefore checkable against runtime evidence. `unresolved`
    are prose fragments ('fable brain', 'spread.html', bracketed task lists)
    that make no checkable claim and must never be scored as a miss.
    """
    if not agent_field or not agent_field.strip():
        return [], []
    resolved, unresolved = [], []
    for raw in LEG_SPLIT.split(agent_field):
        n = norm(raw).strip("[]")
        if not n or n in NOT_AN_AGENT:
            continue
        if registry is None:
            resolved.append(n)
            continue
        if n in registry:
            resolved.append(n)
            continue
        # Tolerate decorated legs like 'executor legs' or 'opus executor'
        # by looking for a registry name contained in the fragment.
        hit = next((k for k in registry
                    if len(k) > 4 and (k in n or n in k)), None)
        (resolved.append(hit) if hit else unresolved.append(n))
    return resolved, unresolved


def first_record(jsonl: Path) -> dict:
    """First line of a subagent transcript carries timestamp / cwd / sessionId."""
    try:
        with jsonl.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    return json.loads(line)
    except Exception:
        pass
    return {}


def parse_ts(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def discover_invocations() -> list[dict]:
    """Walk every subagent meta sidecar the runtime has written."""
    out = []
    if not PROJECTS.is_dir():
        return out
    for meta_path in PROJECTS.glob("*/*/subagents/agent-*.meta.json"):
        agent_id = meta_path.name[len("agent-"):-len(".meta.json")]
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            # Malformed sidecar is a real observation, not a silent skip.
            out.append({"agent_id": agent_id, "malformed": True,
                        "path": str(meta_path)})
            continue

        jsonl = meta_path.with_name(f"agent-{agent_id}.jsonl")
        head = first_record(jsonl) if jsonl.exists() else {}

        # Prefer the transcript's own timestamp; fall back to sidecar mtime.
        started = parse_ts(head.get("timestamp"))
        if started is None:
            try:
                started = datetime.fromtimestamp(meta_path.stat().st_mtime, timezone.utc)
            except Exception:
                started = None

        out.append({
            "agent_id": agent_id,
            "agent_type": meta.get("agentType"),
            "agent_type_norm": norm(meta.get("agentType") or ""),
            "description": meta.get("description"),
            "tool_use_id": meta.get("toolUseId"),
            "spawn_depth": meta.get("spawnDepth"),
            "parent_agent_id": meta.get("parentAgentId"),
            "model": meta.get("model"),
            # session uuid from the transcript body is authoritative; the
            # directory name can disagree (worktrees, renamed projects).
            "session_uuid": head.get("sessionId") or meta_path.parent.parent.name,
            "cwd": head.get("cwd"),
            "git_branch": head.get("gitBranch"),
            "cc_version": head.get("version"),
            "started_at": started.isoformat() if started else None,
            "_started": started,
            "project_slug": meta_path.parent.parent.parent.name,
            "transcript": str(jsonl),
        })
    return out


def observed_sessions(invocations) -> dict:
    """project_slug -> set of session uuids we have any evidence for."""
    idx = collections.defaultdict(set)
    for inv in invocations:
        if inv.get("malformed"):
            continue
        idx[inv["project_slug"]].add(inv["session_uuid"])
    return idx


def load_routes() -> list[dict]:
    rows = []
    if not CORTEX_LOG.exists():
        return rows
    for line in CORTEX_LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def reconcile(routes, invocations, window_minutes=90, session_key=None):
    """
    Join routes to observed invocations.

    session_key: name of the cortex-log field holding the real Claude Code
    session UUID. When present the join is exact. When absent (the situation
    today, where session_id is a UTC hour bucket) we fall back to a
    project+time-window approximation and mark every such row low confidence.
    """
    by_depth1 = [i for i in invocations
                 if not i.get("malformed") and i.get("spawn_depth") == 1 and i["_started"]]
    registry = load_agent_registry()

    # A session key that is absent from the log silently yields zero candidates
    # for every route, which renders as a confident wall of `not_invoked`.
    # That is the exact failure this tool exists to prevent, so refuse it.
    if session_key is not None:
        present = sum(1 for r in routes if r.get(session_key))
        if present == 0:
            raise SystemExit(
                f"refusing to reconcile: --session-key '{session_key}' is present in "
                f"0 of {len(routes)} routes.\n"
                "Every route would be scored 'not_invoked' on missing data rather than "
                "on evidence.\nOmit --session-key to run the low-confidence "
                "project+time approximation instead."
            )
        if present < len(routes):
            print(f"  WARNING: '{session_key}' present in only {present}/{len(routes)} "
                  f"routes; the remainder are reported as no_evidence, not as negatives.",
                  file=sys.stderr)
    exact = session_key is not None

    # Order routes so each route's window ends where the next one begins.
    routes = sorted(routes, key=lambda r: r.get("ts") or "")
    results = []

    for idx, r in enumerate(routes):
        rts = parse_ts(r.get("ts"))
        legs, unresolved = declared_legs(r.get("agent") or "", registry)

        # Window: this route's ts until the next route in the same scope.
        end = rts + timedelta(minutes=window_minutes) if rts else None
        for later in routes[idx + 1:]:
            lts = parse_ts(later.get("ts"))
            if lts and rts and lts > rts and later.get("project") == r.get("project"):
                end = min(end, lts) if end else lts
                break

        cands, ambiguous = [], False
        if rts and end:
            if exact:
                sid = r.get(session_key)
                if not sid:
                    # No key on this row: unobservable, not a negative.
                    ambiguous = True
                else:
                    cands = [i for i in by_depth1
                             if i["session_uuid"] == sid and rts <= i["_started"] < end]
            else:
                proj = (r.get("project") or "").lower()
                for i in by_depth1:
                    slug = (i["project_slug"] or "").lower()
                    cwd = (i["cwd"] or "").lower()
                    if proj and (proj in slug or proj in cwd) and rts <= i["_started"] < end:
                        cands.append(i)
                # Concurrent sessions in the same repo make attribution unsafe.
                if len({c["session_uuid"] for c in cands}) > 1:
                    ambiguous = True

        observed = {c["agent_type_norm"] for c in cands}
        matched = [l for l in legs if l in observed]
        missing = [l for l in legs if l not in observed]
        extra = sorted(observed - set(legs))

        # Can we even see this route's session?
        proj = (r.get("project") or "").lower()
        session_visible = any(
            proj and proj in slug.lower()
            for slug in observed_sessions(invocations)
        )

        if ambiguous:
            verdict = NO_EVIDENCE
        elif not legs and unresolved:
            # The field was filled in, but with prose that names no agent.
            # Unscoreable by construction — a declaration-side defect.
            verdict = UNRESOLVED
        elif legs and matched and not missing:
            verdict = MATCH
        elif legs and matched and missing:
            verdict = PARTIAL
        elif legs and not matched and observed:
            verdict = SUBSTITUTED
        elif legs and not observed:
            # Only a confirmed negative if we can see the project at all.
            verdict = NOT_INVOKED if session_visible else NO_EVIDENCE
        elif not legs and observed:
            verdict = UNDECLARED
        elif not legs and not observed:
            verdict = CONSISTENT_DIRECT if session_visible else NO_EVIDENCE
        else:
            verdict = NO_EVIDENCE

        results.append({
            "ts": r.get("ts"),
            "task_hash": r.get("task_hash"),
            "project": r.get("project"),
            "tier": r.get("tier"),
            "system": r.get("system"),
            "pattern": r.get("pattern"),
            "agent_declared": r.get("agent"),
            "declared_legs": legs,
            "declared_unresolved": unresolved,
            "agent_invoked": sorted(observed),
            "invoked_detail": [
                {"agent_type": c["agent_type"], "agent_id": c["agent_id"],
                 "model": c["model"], "started_at": c["started_at"]}
                for c in cands
            ],
            "matched": matched,
            "missing": missing,
            "unexpected": extra,
            "verdict": verdict,
            "join": "exact" if exact else "approx_project_time",
            "join_confidence": "high" if exact else "low",
        })
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write full reconciliation records here")
    ap.add_argument("--snapshot", help="copy meta sidecars into this dir (hedge against retention cleanup)")
    ap.add_argument("--window", type=int, default=90, help="max route window in minutes")
    ap.add_argument("--session-key", default=None,
                    help="cortex-log field holding the real CC session uuid (enables exact join)")
    args = ap.parse_args()

    invocations = discover_invocations()
    routes = load_routes()

    depth = collections.Counter(i.get("spawn_depth") for i in invocations)
    malformed = sum(1 for i in invocations if i.get("malformed"))

    print(f"observed subagent invocations : {len(invocations)}")
    print(f"  malformed sidecars          : {malformed}")
    print(f"  by spawn_depth              : {dict(sorted(depth.items(), key=lambda x: (x[0] is None, x[0])))}")
    print(f"  distinct sessions            : {len({i.get('session_uuid') for i in invocations})}")
    print(f"routes in cortex-log          : {len(routes)}")

    blank = sum(1 for r in routes if not (r.get('agent') or '').strip())
    print(f"  routes with blank agent      : {blank} ({blank * 100 // max(len(routes), 1)}%)")

    res = reconcile(routes, invocations, args.window, args.session_key)
    verdicts = collections.Counter(x["verdict"] for x in res)
    print("\nreconciliation verdicts:")
    for k, v in verdicts.most_common():
        print(f"  {k:<20} {v:>4}  ({v * 100 // max(len(res), 1)}%)")

    if not args.session_key:
        print("\n  NOTE: no session key given, so every verdict above rests on a")
        print("  project+time-window approximation. Treat as directional only.")

    if args.snapshot:
        dest = Path(args.snapshot)
        dest.mkdir(parents=True, exist_ok=True)
        n = 0
        for meta_path in PROJECTS.glob("*/*/subagents/agent-*.meta.json"):
            tgt = dest / f"{meta_path.parent.parent.name}__{meta_path.name}"
            if not tgt.exists():
                tgt.write_text(meta_path.read_text())
                n += 1
        print(f"\nsnapshotted {n} new sidecars into {dest}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"invocations": [{k: v for k, v in i.items() if not k.startswith("_")}
                             for i in invocations],
             "reconciliation": res}, indent=2))
        print(f"wrote {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
