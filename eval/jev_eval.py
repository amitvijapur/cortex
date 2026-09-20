#!/usr/bin/env python3
"""Jev pilot replay. Defaults to synthetic plumbing fixtures, never paid calls.

History is diagnostic evidence, not a quality label. Quality is withheld until
reviewed held-out labels and comparable real session decisions are supplied.
"""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO / "eval/fixtures/jev-cases.json"
SCHEMA = "cortex-jev-evaluation-v1"
ARMS = ("baseline", "shadow", "advisory")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def source_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name, path):
    from importlib.machinery import SourceFileLoader
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = load_module("jev_eval_cli", REPO / "bin/cortex")


def validate_dataset(data):
    """Prevent accidental label exposure and repeated-task leakage across splits."""
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("dataset needs nonempty cases")
    seen, groups, tasks = set(), {}, {}
    history = data.get("history", [])
    if not isinstance(history, list) or not all(isinstance(e, dict) for e in history):
        raise ValueError("history must be an ordered raw event list")
    for case in data["cases"]:
        cid, group, split = case.get("id"), case.get("group"), case.get("split")
        if not isinstance(cid, str) or not cid or cid in seen:
            raise ValueError("case IDs must be unique nonempty strings")
        seen.add(cid)
        if not isinstance(group, str) or not group or split not in ("tune", "heldout"):
            raise ValueError("each case needs a group and tune/heldout split")
        if group in groups and groups[group] != split:
            raise ValueError("repeated group crosses tune/heldout split")
        groups[group] = split
        task = case.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a nonempty string")
        normalized = " ".join(task.lower().split())
        if normalized in tasks and tasks[normalized] != group:
            raise ValueError("identical tasks must share a group")
        tasks[normalized] = group
        prefix = case.get("history_prefix", 0)
        if type(prefix) is not int or not 0 <= prefix <= len(history):
            raise ValueError("history_prefix must index the raw events available at query time")
        # A target event must be outside its own prefix, even if class/route coincide.
        target = case.get("target_event_index")
        if target is not None and (type(target) is not int or not prefix <= target < len(history)):
            raise ValueError("target event or future events leak into history prefix")
        labels = case.get("labels", {})
        if labels.get("reviewed"):
            if not labels.get("reviewer") or not labels.get("provenance") or not labels.get("reviewed_at"):
                raise ValueError("reviewed labels require reviewer, provenance and reviewed_at")
            if not labels.get("acceptable_candidates") or not labels.get("acceptable_classes"):
                raise ValueError("reviewed labels require nonempty acceptable candidate/class sets")
    return data


def hint_context(case, raw):
    """Run the actual current hint renderer over the query-time raw prefix only.

    Do not collapse the full log before slicing: that leaks later corrections.
    The session's independently supplied query_class is not a gold class label.
    """
    prefix = copy.deepcopy(raw[:case.get("history_prefix", 0)])
    entries = CLI.collapse(prefix)
    args = SimpleNamespace(task=case["task"], classification=case.get("query_class"),
                           tier=None, min_similarity=None, top=5)
    stream = io.StringIO()
    start = time.perf_counter()
    with patch.object(CLI, "read_log", return_value=entries), contextlib.redirect_stdout(stream):
        CLI.cmd_hint(args)
    elapsed = (time.perf_counter() - start) * 1000
    return {"task": case["task"], "query_class": case.get("query_class"),
            "explicit_candidate": case.get("explicit_candidate"),
            "hint": stream.getvalue()}, entries, elapsed


def classifier_input(case):
    # Deliberately no query_class, labels, expected route, reason or outcome.
    return case["task"]


def advice_hash(record):
    return fingerprint({k: record.get(k) for k in (
        "status", "classification", "candidate_id", "confidence", "probabilities",
        "fallback_reason", "model", "returned_model", "criteria_version")})


def number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def accounting(attempts):
    """All attempts, including failed/retried calls; unknown is never free."""
    if not isinstance(attempts, list) or not all(isinstance(a, dict) for a in attempts):
        raise ValueError("attempts must be a list of accounting objects")
    known = sum(a["cost_usd"] for a in attempts if number(a.get("cost_usd")))
    missing_cost = sum(not number(a.get("cost_usd")) for a in attempts)
    missing_latency = sum(not number(a.get("latency_ms")) for a in attempts)
    return {"attempt_count": len(attempts), "known_cost_usd": known,
            "unknown_cost_attempts": missing_cost,
            "cost_usd": None if missing_cost else known,
            "latency_ms": None if missing_latency else sum(a["latency_ms"] for a in attempts)}


def adviser_accounting(record):
    attempts = record.get("attempts")
    if attempts is not None:
        result = accounting(attempts)
        # A lost attempt must not silently disappear from the denominator.
        if len(attempts) != record.get("request_count"):
            raise ValueError("Jev attempt count does not match request_count")
        return result
    count = record.get("request_count")
    if type(count) is not int or count < 0:
        raise ValueError("invalid Jev request_count")
    if count == 0:
        return {"attempt_count": 0, "known_cost_usd": 0, "unknown_cost_attempts": 0,
                "cost_usd": 0, "latency_ms": record.get("latency_ms", 0)}
    # Runtime aggregate cost covers all attempted calls. Missing aggregate stays unknown.
    cost = record.get("cost_usd")
    return {"attempt_count": count, "known_cost_usd": cost if number(cost) else 0,
            "unknown_cost_attempts": 0 if number(cost) else count,
            "cost_usd": cost if number(cost) else None,
            "latency_ms": record.get("latency_ms") if number(record.get("latency_ms")) else None}


def quantiles(values):
    values = sorted(v for v in values if number(v))
    def percentile(p):
        return values[max(0, math.ceil(p * len(values)) - 1)] if values else None
    return {"n": len(values), "p50": percentile(.5), "p95": percentile(.95)}


def load_session_runs(document, rows, candidates_hash):
    """Only accept real, matched session outputs, never fabricate final routes.

    A session run's attempts includes its routing and fallback/retry work exactly
    once, excluding adviser calls. The model and protocol must match across arms.
    """
    indexed, signatures = {}, {}
    by_id = {r["id"]: r for r in rows}
    for run in document.get("runs", []):
        cid, arm = run.get("case_id"), run.get("arm")
        if cid not in by_id or arm not in ARMS or (cid, arm) in indexed:
            raise ValueError("unknown or duplicate session run")
        row = by_id[cid]
        if run.get("context_hash") != row["context_hash"] or run.get("candidates_hash") != candidates_hash:
            raise ValueError("session context or candidate pool mismatch")
        if not run.get("model") or not run.get("protocol_hash") or run.get("synthetic", True):
            raise ValueError("session runs need real provenance, model and protocol_hash")
        signature = (run["model"], run["protocol_hash"])
        if cid in signatures and signatures[cid] != signature:
            raise ValueError("session model/protocol mismatch across arms")
        signatures[cid] = signature
        if arm == "advisory" and run.get("advice_hash") != row["advice_hash"]:
            raise ValueError("advisory session did not receive this advice")
        if arm != "advisory" and run.get("advice_visible", False):
            raise ValueError("baseline/shadow session must not see experimental advice")
        if not isinstance(run.get("attempts"), list) or not run["attempts"]:
            raise ValueError("session runs must include all attempts, including fallbacks")
        # Total wall time includes hint and all sequential/parallel session work.
        if not number(run.get("end_to_end_ms")):
            raise ValueError("session run requires measured end_to_end_ms")
        indexed[cid, arm] = run
    return indexed


def arm_metrics(selected, labels, ids, quality_ready, scored_ids):
    costs, latencies, request_count, unknown = [], [], 0, 0
    reroutes = []
    for row, run in selected:
        session = accounting(run["attempts"])
        adviser = adviser_accounting(row["jev"]) if run["arm"] != "baseline" else {"cost_usd": 0, "attempt_count": 0, "unknown_cost_attempts": 0}
        cost = None if session["cost_usd"] is None or adviser["cost_usd"] is None else session["cost_usd"] + adviser["cost_usd"]
        costs.append(cost)
        unknown += session["unknown_cost_attempts"] + adviser["unknown_cost_attempts"]
        request_count += session["attempt_count"] + adviser["attempt_count"]
        latencies.append(run["end_to_end_ms"])
        if type(run.get("reroutes")) is int and run["reroutes"] >= 0:
            reroutes.append(run["reroutes"])
    scored = [(r, run) for r, run in selected if r["id"] in scored_ids]
    return {
        "session_cases": len(selected), "request_count": request_count if selected else None,
        "total_cost_usd": sum(costs) if selected and all(c is not None for c in costs) else None,
        "known_case_cost_usd": sum(c for c in costs if c is not None),
        "unknown_cost_attempts": unknown,
        "end_to_end_latency_ms": quantiles(latencies),
        "reroutes": sum(reroutes) if selected and len(reroutes) == len(selected) else None,
        "unavailable_candidate_errors": sum(run.get("candidate_id") not in ids | {"abstain"} for _, run in selected),
        "session_abstentions": sum(run.get("candidate_id") == "abstain" for _, run in selected),
        "explicit_choice_violations": sum(r["context"].get("explicit_candidate") is not None
                                           and run.get("candidate_id") != "abstain"
                                           and run.get("candidate_id") != r["context"]["explicit_candidate"]
                                           for r, run in selected),
        "workflow_accuracy": sum(run.get("candidate_id") in labels[r["id"]]["acceptable_candidates"] for r, run in scored) / len(scored) if quality_ready and scored else None,
        "classification_accuracy": sum(run.get("classification") in labels[r["id"]]["acceptable_classes"] for r, run in scored) / len(scored) if quality_ready and scored else None,
    }


def summarize(rows, cases, sessions, candidates, live):
    ids = {c["id"] for c in candidates}
    labels = {c["id"]: c.get("labels", {}) for c in cases}
    heldout = {c["id"] for c in cases if c["split"] == "heldout"}
    reviewed = {cid for cid in heldout if labels[cid].get("reviewed")}
    suggested = [r for r in rows if r["jev"].get("status") == "suggested"]
    invalid = [r for r in suggested if r["jev"].get("candidate_id") not in ids]
    paired = heldout & {r["id"] for r in rows if all((r["id"], a) in sessions for a in ARMS)}
    comparable = reviewed & paired
    has_live_response = any(r["id"] in heldout and r["jev"].get("request_count", 0) > 0
                            and r["jev"].get("returned_model") == r["jev"].get("model")
                            for r in rows)
    quality_ready = bool(heldout) and reviewed == heldout and comparable == heldout and live and has_live_response
    result = {
        "cases": len(rows), "suggestions": len(suggested),
        "coverage": len(suggested) / len(rows) if rows else None,
        "abstention_or_fallback_rate": sum(r["jev"].get("status") == "fallback" for r in rows) / len(rows) if rows else None,
        "unavailable_candidate_errors": len(invalid),
        "fallback_reasons": {}, "reviewed_heldout_cases": len(reviewed),
        "comparable_heldout_cases": len(comparable), "quality_ready": quality_ready,
        "quality": None,
        "added_jev_latency_ms": quantiles([r["jev"].get("latency_ms") for r in rows]),
        "hint_latency_ms": quantiles([r["hint_latency_ms"] for r in rows]),
        "arms": {},
        "paired_heldout": {"case_ids": sorted(paired), "denominator": len(paired), "arms": {}},
        "recommendation": "keep_off; shadow collection only until reviewed held-out real session comparisons justify advisory",
        "existing_calls_avoided": None,
    }
    for row in rows:
        reason = row["jev"].get("fallback_reason")
        if reason:
            result["fallback_reasons"][reason] = result["fallback_reasons"].get(reason, 0) + 1
    if quality_ready:
        offered = [r for r in suggested if r["id"] in heldout]
        result["quality"] = {
            "jev_conditional_workflow_accuracy": sum(r["jev"].get("candidate_id") in labels[r["id"]]["acceptable_candidates"] for r in offered) / len(offered) if offered else None,
            "jev_conditional_class_accuracy": sum(r["jev"].get("classification") in labels[r["id"]]["acceptable_classes"] for r in offered) / len(offered) if offered else None,
            "denominator": len(offered),
            "note": "Descriptive held-out accuracy; no automatic rollout decision or statistical benefit claim.",
        }
    for arm in ARMS:
        selected = [(r, sessions[r["id"], arm]) for r in rows if (r["id"], arm) in sessions]
        result["arms"][arm] = arm_metrics(selected, labels, ids, quality_ready, heldout)
        result["paired_heldout"]["arms"][arm] = arm_metrics(
            [(r, run) for r, run in selected if r["id"] in paired], labels, ids, quality_ready, paired)
    all_jev = [adviser_accounting(r["jev"]) for r in rows]
    result["jev_only"] = {
        "request_count": sum(a["attempt_count"] for a in all_jev),
        "cost_usd": sum(a["cost_usd"] for a in all_jev) if all(a["cost_usd"] is not None for a in all_jev) else None,
        "known_cost_usd": sum(a["known_cost_usd"] for a in all_jev),
        "unknown_cost_attempts": sum(a["unknown_cost_attempts"] for a in all_jev),
    }
    all_sessions = [accounting(run["attempts"]) for run in sessions.values()]
    collected = all_jev + all_sessions
    result["collection_totals"] = {
        "request_count": sum(a["attempt_count"] for a in collected),
        "known_cost_usd": sum(a["known_cost_usd"] for a in collected),
        "cost_usd": sum(a["cost_usd"] for a in collected) if all(a["cost_usd"] is not None for a in collected) else None,
        "unknown_cost_attempts": sum(a["unknown_cost_attempts"] for a in collected),
        "note": "Collected Jev calls counted once; arm scenario totals are not additive.",
    }
    return result


def fixture_record(case, mode):
    """Explicitly fabricated adviser output, used only for plumbing/accounting."""
    if mode == "off":
        return {"status": "off", "request_count": 0, "cost_usd": 0,
                "latency_ms": 0, "model": "fixture-only", "criteria_version": "fixture-v1"}
    record = copy.deepcopy(case.get("fixture", {}))
    record.setdefault("status", "fallback")
    record.setdefault("fallback_reason", "fixture_abstention" if record["status"] == "fallback" else None)
    record.setdefault("request_count", 1)
    record.setdefault("cost_usd", None)
    record.setdefault("latency_ms", 4)
    record.update(model="fixture-only", criteria_version="fixture-v1", synthetic=True)
    return record


def evaluate(data, candidates, *, mode="shadow", model="jev-1.13.0", threshold=.8,
             live=False, manifest=None, session_id=None, max_calls=0, records=None, session_document=None):
    validate_dataset(data)
    if mode not in ("off", "shadow", "advisory"):
        raise ValueError("invalid mode")
    if not number(threshold) or threshold > 1:
        raise ValueError("threshold must be a finite number between zero and one")
    if not isinstance(model, str) or not re.fullmatch(r"jev-\d+\.\d+\.\d+", model):
        raise ValueError("evaluation requires a pinned Jev version, not a rolling alias")
    if not candidates or len({c["id"] for c in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be nonempty and unique")
    ids = {c["id"] for c in candidates}
    capabilities = (manifest or data).get("capabilities", [])
    for case in data["cases"]:
        if case.get("labels", {}).get("reviewed") and not set(case["labels"]["acceptable_candidates"]).issubset(ids | {"abstain"}):
            raise ValueError("reviewed labels reference candidates outside the evaluated pool")
    inputs = {"dataset_hash": fingerprint(data), "candidates_hash": fingerprint(candidates),
              "capabilities_hash": fingerprint(capabilities),
              "model": model, "threshold": threshold, "mode": mode,
              "cli_hash": source_hash(REPO / "bin/cortex"),
              "harness_hash": source_hash(Path(__file__)),
              "runtime_hash": source_hash(REPO / "bin/cortex_jev.py") if (REPO / "bin/cortex_jev.py").exists() else None}
    runtime = None
    if live:
        if records or not manifest or not session_id or max_calls < 1 or mode == "off":
            raise ValueError("live needs manifest, independently supplied session ID, non-off mode and positive --max-calls")
        runtime = load_module("jev_eval_runtime", REPO / "bin/cortex_jev.py")
        # Production batches the two independent questions into one request, no retries.
        if max_calls < len(data["cases"]):
            raise ValueError("--max-calls must reserve one request per case")
        runtime.validate_manifest(manifest, session_id)
    if records and (records.get("schema") != SCHEMA or records.get("inputs") != inputs):
        raise ValueError("recorded evaluation fingerprint mismatch")
    if records and records.get("execution") == "live" and any(
            r["jev"].get("synthetic") or r["jev"].get("model") == "fixture-only"
            for r in records.get("rows", [])):
        raise ValueError("synthetic adviser records cannot be relabelled live")
    recorded = {r["id"]: r for r in records["rows"]} if records else {}
    rows = []
    calls = 0
    for case in data["cases"]:
        context, entries, hint_ms = hint_context(case, data.get("history", []))
        context["capabilities_hash"] = inputs["capabilities_hash"]
        context_hash = fingerprint(context)
        if records:
            prior = recorded.get(case["id"])
            if not prior or prior["context_hash"] != context_hash:
                raise ValueError("recorded case context mismatch")
            record = prior["jev"]
        elif live:
            if calls + 1 > max_calls:
                raise ValueError("live request ceiling reached")
            record = runtime.advise(classifier_input(case), manifest, mode=mode,
                                    session_id=session_id, model=model,
                                    threshold=threshold, explicit_candidate=case.get("explicit_candidate"))
            calls += record["request_count"]
        else:
            record = fixture_record(case, mode)
        historical = case.get("historical_candidate_id")
        rows.append({"id": case["id"], "group": case["group"], "split": case["split"],
                     "context": context, "context_hash": context_hash,
                     "advice_hash": advice_hash(record), "jev": record,
                     "hint_latency_ms": hint_ms,
                     "historical_route_agreement_diagnostic": (record.get("candidate_id") == historical) if historical and record.get("status") == "suggested" else None})
    real = live or bool(records and records.get("execution") == "live")
    sessions = load_session_runs(session_document or {}, rows, inputs["candidates_hash"])
    return {"schema": SCHEMA, "execution": "live" if real else "synthetic_plumbing_only",
            "inputs": inputs, "capabilities": capabilities, "candidates": candidates, "rows": rows,
            "summary": summarize(rows, data["cases"], sessions, candidates, real),
            "limitations": ["Historical agreement is not routing quality.",
                            "Missing costs remain unknown, including failed requests.",
                            "Fixture adviser answers are fabricated and measure plumbing only.",
                            "Session end-to-end time must include advice wait and all fallback work.",
                            "No existing model call savings are established."]}


def read_json(path):
    return json.loads(Path(path).read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--session-id",
                        help="current host session ID, independently supplied or host environment")
    parser.add_argument("--mode", choices=("off", "shadow", "advisory"), default="shadow")
    parser.add_argument("--model", default="jev-1.13.0")
    parser.add_argument("--threshold", type=float, default=.8)
    parser.add_argument("--live", action="store_true", help="authorize paid Jev calls")
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--records", type=Path, help="reuse matching prior report without Jev calls")
    parser.add_argument("--session-runs", type=Path)
    parser.add_argument("--out", type=Path, help="new experimental report; never a production log")
    args = parser.parse_args(argv)
    try:
        host_session = next((os.environ[k] for k in (
            "CORTEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID",
            "CODEX_THREAD_ID") if os.environ.get(k)), None)
        if args.live and args.session_id and host_session and args.session_id != host_session:
            raise ValueError("session_mismatch: explicit ID conflicts with current host")
        sid = args.session_id or host_session
        if args.out and args.out.exists():
            raise ValueError("output already exists; choose a new report path")
        if args.out and args.out.name in {"cortex-log.jsonl", "cortex-inbox.jsonl", "cortex-install-queue.jsonl"}:
            raise ValueError("output must not be a production state file")
        data = read_json(args.dataset)
        manifest = read_json(args.manifest) if args.manifest else None
        candidates = manifest["candidates"] if manifest else data["candidates"]
        report = evaluate(data, candidates, mode=args.mode, model=args.model,
                          threshold=args.threshold, live=args.live, manifest=manifest,
                          session_id=sid,
                          max_calls=args.max_calls,
                          records=read_json(args.records) if args.records else None,
                          session_document=read_json(args.session_runs) if args.session_runs else None)
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.out:
            # Exclusive creation makes output isolation explicit and never appends to logs.
            with args.out.open("x") as stream:
                stream.write(rendered)
        else:
            print(rendered, end="")
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"jev evaluation refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
