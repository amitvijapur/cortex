#!/usr/bin/env python3
"""Isolated evaluation regressions. No model processes or personal state access."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Resolve imported defaults inside a disposable home as well as redirecting outputs.
_home = tempfile.TemporaryDirectory(prefix="cortex-evaluation-tests-")
with patch.dict(os.environ, {"HOME": _home.name, "CORTEX_HOME": _home.name}):
    import hint_arms
    import route_eval
    import score_adherence
    import eval_retrieval


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cortex-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch.dict(os.environ, {
            "HOME": str(self.root), "CORTEX_HOME": str(self.root)}))
        # A stray subprocess is a test failure, not a paid model invocation.
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("unexpected process")))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.object(route_eval, "CLAUDE_DIR", self.root))
        self.enterContext(patch.object(route_eval.shutil, "which", return_value="mock-claude"))
        for name in ("cortex.md", "CLAUDE.md"):
            (self.root / name).write_text("fixture " + name)
        self.cases = [{"id": cid, "kind": "rule", "task": cid,
                       "assert": [{"type": "tier_equals", "value": "L2"}]}
                      for cid in ("first", "second")]
        self.spec = self.root / "cases.json"
        self.spec.write_text(json.dumps({"cases": self.cases}))
        self.out = self.root / "run.json"
        self.good = {"raw": "Direct > fix @ L2",
                     "route": route_eval.parse_route("Direct > fix @ L2"),
                     "error": None, "cost_usd": 0}

    def run_eval(self, *args, result=None):
        argv = ["route_eval", "--cases", str(self.spec), "--out", str(self.out),
                "--no-batch", "--max-spend", "100", *args]
        with patch.object(sys, "argv", argv), patch.object(
                route_eval, "run_case", side_effect=lambda *a: copy.deepcopy(
                    self.good if result is None else result)) as run:
            code = route_eval.main()
        return code, run.call_count

    def test_successful_run_skips_but_legacy_and_corrupt_reports_do_not(self):
        self.assertEqual(self.run_eval(), (0, 2))
        self.assertEqual(self.run_eval("--if-changed"), (0, 0))
        self.out.write_text(json.dumps({"cortex_md_sha": route_eval.sha(self.root / "cortex.md")}))
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))
        self.out.write_text("{unfinished")
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))

    def test_interrupted_rerun_invalidates_cache_and_preserves_explicit_report(self):
        for error in (RuntimeError("worker interrupted"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(self.run_eval(), (0, 2))
                previous = self.out.read_bytes()
                argv = ["route_eval", "--cases", str(self.spec), "--out", str(self.out),
                        "--no-batch"]

                def interrupt(*args):
                    pending = json.loads(self.out.read_text())
                    self.assertEqual(pending["attempt_status"], "incomplete")
                    self.assertFalse(pending["successful"])
                    raise error

                with patch.object(sys, "argv", argv), patch.object(
                        route_eval, "run_case", side_effect=interrupt):
                    with self.assertRaises(type(error)):
                        route_eval.main()
                pending = self.out.read_bytes()
                self.assertEqual(json.loads(pending)["attempt_status"], "incomplete")
                archives = self.out.parent / f".{self.out.name}.history"
                self.assertIn(previous, [p.read_bytes() for p in archives.iterdir()])
                self.assertEqual(self.run_eval("--if-changed"), (0, 2))
                self.assertIn(pending, [p.read_bytes() for p in archives.iterdir()])

    def test_interrupted_default_run_does_not_fall_back_to_previous_success(self):
        argv = ["route_eval", "--cases", str(self.spec), "--no-batch"]
        with patch.object(sys, "argv", argv), patch.object(
                route_eval, "run_case", return_value=self.good):
            self.assertEqual(route_eval.main(), 0)
        original = next((self.root / "eval").glob("run-*.json"))
        # Simulate an existing report with the former second-precision filename.
        stamp = json.loads(original.read_text())["ts"][:19]
        old_name = "run-" + stamp.replace("-", "").replace(":", "") + "Z.json"
        original = original.rename(original.with_name(old_name))
        evidence = original.read_bytes()
        with patch.object(sys, "argv", argv), patch.object(
                route_eval, "run_case", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                route_eval.main()
        self.assertEqual(original.read_bytes(), evidence)
        self.assertEqual(len(list((self.root / "eval").glob("run-*.json"))), 2)
        with patch.object(sys, "argv", argv + ["--if-changed"]), patch.object(
                route_eval, "run_case", return_value=self.good) as run:
            self.assertEqual(route_eval.main(), 0)
            self.assertEqual(run.call_count, 2)
        self.assertEqual(original.read_bytes(), evidence)

    def test_atomic_report_failure_preserves_previous_bytes(self):
        self.run_eval()
        previous = self.out.read_bytes()
        with patch.object(route_eval.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                route_eval.write_report(self.out, {"successful": False})
        self.assertEqual(self.out.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".report-*")), [])

    def test_incomplete_publish_failure_starts_no_workers(self):
        self.run_eval()
        previous = self.out.read_bytes()
        argv = ["route_eval", "--cases", str(self.spec), "--out", str(self.out), "--no-batch"]
        with patch.object(sys, "argv", argv), patch.object(
                route_eval, "write_report", side_effect=OSError("cannot record attempt")), patch.object(
                route_eval, "run_case") as run:
            with self.assertRaisesRegex(OSError, "cannot record attempt"):
                route_eval.main()
            run.assert_not_called()
        self.assertEqual(self.out.read_bytes(), previous)

    def test_completed_publish_failure_leaves_incomplete_attempt(self):
        self.run_eval()
        original_replace = os.replace

        def fail_completed(source, destination):
            if Path(destination) == self.out:
                report = json.loads(Path(source).read_text())
                if report.get("attempt_status") == "complete":
                    raise OSError("completion publish failed")
            return original_replace(source, destination)

        with patch.object(route_eval.os, "replace", side_effect=fail_completed):
            with self.assertRaisesRegex(OSError, "completion publish failed"):
                self.run_eval()
        self.assertEqual(json.loads(self.out.read_text())["attempt_status"], "incomplete")
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))

    def test_dry_run_and_spend_refusal_preserve_evidence_without_new_attempt(self):
        self.run_eval()
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.run_eval("--dry-run"), (0, 0))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_eval("--max-spend", "0"), (2, 0))
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                  for p in self.root.rglob("*") if p.is_file()})

    def test_failed_refused_or_incomplete_runs_never_skip(self):
        bad_route = dict(self.good, route=route_eval.parse_route("Direct > fix @ L4"))
        refusal = dict(self.good, route=route_eval.parse_route("Direct > refuse @ L2"))
        for result in ({"error": "timeout", "cost_usd": 0}, bad_route, refusal):
            with self.subTest(result=result):
                self.assertEqual(self.run_eval(result=result)[0], 1)
                self.assertEqual(self.run_eval("--if-changed"), (0, 2))
        report = json.loads(self.out.read_text())
        report["results"]["first"]["runs"] = []
        self.out.write_text(json.dumps(report))
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))

    def test_changed_inputs_and_requested_coverage_invalidate_cache(self):
        self.run_eval("--only", "first")
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))
        for name in ("cortex.md", "CLAUDE.md"):
            (self.root / name).write_text("changed " + name)
            self.assertEqual(self.run_eval("--if-changed"), (0, 2))
        self.cases[0]["task"] = "changed task"
        self.spec.write_text(json.dumps({"cases": self.cases}))
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))
        self.assertEqual(self.run_eval("--if-changed", "--model", "different"), (0, 2))
        self.assertEqual(self.run_eval("--if-changed", "--model", "different", "--repeat", "2"), (0, 4))
        self.assertEqual(self.run_eval("--if-changed", "--minimal-env"), (0, 2))

    def test_reuse_rejects_each_manifest_mismatch_and_missing_evidence(self):
        self.run_eval()
        report = json.loads(self.out.read_text())
        for key in report["inputs"]:
            with self.subTest(key=key):
                altered = copy.deepcopy(report["inputs"])
                altered[key] = "different"
                self.assertFalse(route_eval.reusable_run(report, altered))
        for change in ("error", "stable", "missing", "modal", "assertion"):
            altered = copy.deepcopy(report)
            r = altered["results"]["first"]
            if change == "error":
                r["runs"][0]["error"] = "failed despite parseable output"
            elif change == "stable":
                r["stable"] = False
            elif change == "missing":
                del altered["results"]["first"]
            elif change == "modal":
                r["modal"] = None
            else:
                r["modal"]["tier"] = "L4"
                r["runs"][0]["route"]["tier"] = "L4"
            self.assertFalse(route_eval.reusable_run(altered, report["inputs"]))

    def test_cli_errors_cannot_be_scored_as_successful_routes(self):
        for exit_code, is_error in ((1, False), (0, True)):
            payload = {"result": self.good["raw"], "is_error": is_error}
            with patch("subprocess.run", return_value=subprocess.CompletedProcess(
                    [], exit_code, json.dumps(payload), "")):
                self.assertTrue(route_eval.run_case(
                    self.cases[0], "mock", self.root, "mock")["error"])
                payload["result"] = "1. " + self.good["raw"]
            with patch("subprocess.run", return_value=subprocess.CompletedProcess(
                    [], exit_code, json.dumps(payload), "")):
                self.assertTrue(route_eval.run_batch(
                    self.cases[:1], "mock", self.root, "mock")["first"]["error"])

    def test_default_batch_cache_and_dry_run(self):
        argv = ["route_eval", "--cases", str(self.spec), "--if-changed"]
        batch = {c["id"]: copy.deepcopy(self.good) for c in self.cases}
        with patch.object(sys, "argv", argv), patch.object(
                route_eval, "run_batch", return_value=batch) as run:
            self.assertEqual(route_eval.main(), 0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(route_eval.main(), 0)
            self.assertEqual(run.call_count, 1)
            reports = list((self.root / "eval").glob("run-*.json"))
            before = {p: p.read_bytes() for p in reports}
            with patch.object(sys, "argv", argv + ["--dry-run"]):
                self.assertEqual(route_eval.main(), 0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(before, {p: p.read_bytes() for p in reports})

    def test_unstable_and_partially_failed_repeats_are_not_successful(self):
        report = dict(modal=self.good["route"], stable=True, raw=self.good["raw"],
                      runs=[self.good, {"error": "timeout"}])
        self.assertFalse(route_eval.successful_results({"first": report}, self.cases[:1], 2))
        other = dict(self.good, route=route_eval.parse_route("Direct > different @ L2"))
        report.update(runs=[self.good, other], stable=False, indeterminate=True)
        self.assertFalse(route_eval.successful_results({"first": report}, self.cases[:1], 2))

    def test_inputs_changed_during_execution_prevent_success(self):
        def mutate_document(*args):
            (self.root / "CLAUDE.md").write_text("changed during execution")
            return copy.deepcopy(self.good)

        argv = ["route_eval", "--cases", str(self.spec), "--out", str(self.out), "--no-batch"]
        with patch.object(sys, "argv", argv), patch.object(
                route_eval, "run_case", side_effect=mutate_document):
            self.assertEqual(route_eval.main(), 1)
        self.assertFalse(json.loads(self.out.read_text())["successful"])
        self.assertEqual(self.run_eval("--if-changed"), (0, 2))

    def test_empty_selection_and_zero_repeats_are_rejected(self):
        for args in (("--kind", "absent"), ("--repeat", "0"), ("--only", "unknown")):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    self.run_eval(*args)
                self.assertEqual(exc.exception.code, 2)

    def test_repeated_task_executions_keep_their_own_corrections_and_attribution(self):
        projects = self.root / "projects"
        for i in range(2):
            project = projects / f"project-{i}"
            project.mkdir(parents=True)
            session = f"session-{i}"

            def event(time, content, user=False):
                return {"type": "user" if user else "assistant", "sessionId": session,
                        "uuid": session + time, "cwd": f"/projects/project-{i}",
                        "timestamp": f"2026-09-{i + 1:02}T{time}Z",
                        "message": {"content": content if user else [{
                            "type": "tool_use", "id": session + time, "name": "Bash", "input": {"command": content}}]}}

            transcript = [event("09:58:00", "repeat", user=True)]
            if i == 0:
                transcript.append(event("09:59:00", "cortex hint 'repeat' --class debug"))
            transcript.append(event("10:00:00", "cortex log-line 'Direct > fix @ L2' 'repeat' --class debug"))
            if i == 0:
                transcript.append(event("10:05:00", "cortex outcome shipped --ref ev_0"))
            transcript.append(event("10:06:00", "Thanks, continue.", user=True))
            completed = []
            for entry in transcript:
                completed.append(entry)
                if entry['type'] == 'assistant':
                    completed.append(dict(entry, type='user', uuid=entry['uuid'] + '-result',
                        message={'content': [{'type': 'tool_result', 'tool_use_id': entry['uuid'],
                                              'is_error': False, 'content': 'ok'}]}))
            transcript = completed
            (project / (session + ".jsonl")).write_text("\n".join(map(json.dumps, transcript)))

        for digest in (score_adherence.D.task_hash("repeat"), None):
            rows = [dict(event="route", event_id=f"ev_{i}", task="repeat",
                         task_hash=digest, ts=f"2026-09-{i + 1:02}T10:00:00Z",
                         session_ref=f"session-{i}", project=f"project-{i}",
                         system="Direct", pattern="fix", tier="L2", **{"class": "debug"})
                    for i in range(2)]
            rows += [{"event": "outcome", "ref": "ev_0", "outcome": "shipped"},
                     {"event": "reclassify", "ref": "ev_1", "tier": "L3"}]
            log = self.root / "log.jsonl"
            log.write_text("\n".join(map(json.dumps, rows)))
            output = self.root / "adherence.jsonl"
            with patch.object(score_adherence, "build", wraps=score_adherence.build) as build:
                self.assertEqual(score_adherence.main([
                    "--log", str(log), "--projects", str(projects),
                    "--out", str(output)]), 0)
            measured = build.call_args.args[0]
            self.assertEqual([r["session_ref"] for r in measured], ["session-0", "session-1"])
            all_records = [json.loads(line) for line in output.read_text().splitlines()]
            records = [r for r in all_records if r.get("kind") == "route"]
            self.assertEqual([r["event_id"] for r in records], ["ev_0", "ev_1"])
            self.assertEqual([r["outcome"] for r in records], ["shipped", None])
            self.assertEqual([r["tier"] for r in records], ["L2", "L3"])
            self.assertEqual([r["route_ts"] for r in records], [r["ts"] for r in rows[:2]])
            self.assertEqual([r["session"] for r in records], ["session-0", "session-1"])
            expected_method = "anchor-command" if digest else "session_ref"
            self.assertEqual([r["attribution_method"] for r in records], [expected_method] * 2)
            if digest:
                self.assertEqual([r["hint"]["ran"] for r in records], [True, False])
                self.assertEqual([r["outcome_cmd_lag_min"] for r in records], [5.0, None])
                metric = next(m for m in all_records[0]["metrics"] if m["id"] == "hint_before_route")
                self.assertEqual((metric["numerator"], metric["denominator"]), (1, 2))

    def test_nullable_text_matches_empty_text_in_every_arm(self):
        pool = [dict(task=None, tier_reason=None, **{"class": "debug"}),
                dict(task="cache repair", tier_reason="cache", **{"class": "debug"})]
        for arm in hint_arms.ARMS.values():
            for task in (None, "cache"):
                query = dict(task=task, tier_reason=None, **{"class": "debug"})
                normalized = lambda r: {k: "" if v is None else v for k, v in r.items()}
                self.assertEqual([normalized(r) for r in arm(query, pool)],
                                 arm(normalized(query), [normalized(r) for r in pool]))

    def test_abstention_uses_the_same_explicit_ranker_as_main_arm(self):
        # Run the reporting path, while a tiny fake index records ranker choices.
        from types import SimpleNamespace
        agent = SimpleNamespace(description="cache", fields={"name": "cache",
                                "description": "cache", "capabilities": "cache"})
        calls = []

        class Index:
            def __init__(self, *a, **kw):
                self.roster = {"cache": agent}

            def search(self, *a, **kw):
                calls.append(kw)
                return [("cache", 10.0)]

        dev = self.root / "dev.json"
        dev.write_text(json.dumps({"pairs": [{"task": "cache", "label": "cache",
                                             "invented_label": "cache"}]}))
        with patch.object(eval_retrieval, "AgentIndex", Index), patch.object(
                eval_retrieval, "load_roster", return_value={"cache": agent}), patch.object(
                eval_retrieval, "enrich_descriptions", side_effect=lambda roster: roster), patch.object(
                eval_retrieval, "search_with_abstain", wraps=eval_retrieval.search_with_abstain) as abstain, patch.object(
                sys, "argv", ["eval_retrieval", "--dev", str(dev)]):
            eval_retrieval.main()
        self.assertEqual(abstain.call_args.kwargs["ranker"], "bm25f")
        self.assertTrue(calls)
        self.assertTrue(all(c["ranker"] == "bm25f" for c in calls))


class HostEvidenceTests(unittest.TestCase):
    """Synthetic evidence only, with every process launch forbidden."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cortex-host-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("unexpected process")))
        self.D = score_adherence.D
        self.start = "2026-09-18T10:00:00Z"
        self.row = dict(ts=self.start, task="fixture task", task_hash=self.D.task_hash("fixture task"),
                        tier="L2", system="Direct", session_ref="session-a")
        command = "cortex log-line 'Direct > fix @ L2' 'fixture task'"
        self.sessions = {"session-a": {"host": "claude", "files": [], "events": [
            self.event(self.start, command),
            self.event("2026-09-18T10:05:00Z"),
        ]}}
        self.index, self.times = self.D.build_anchor_index(self.sessions)

    def event(self, ts, command=None):
        return self.D.Event(self.D.parse_ts(ts), "tool_use" if command else "user",
                            "session-a", ts, None, tool="Bash" if command else None,
                            cmd=command, text="continue" if not command else "",
                            completed_at=self.D.parse_ts(ts) if command else None)

    def attr(self, row):
        return self.D.attribute(row, self.index, self.times, self.sessions)

    def test_mixed_hosts_and_periods_keep_unknowns_and_never_infer_host(self):
        rows = [dict(self.row, host="claude"), dict(self.row, host="codex"),
                dict(self.row, host="other", ts="2026-10-01T00:00:00Z"),
                dict(self.row, system="Codex", model="gpt-example"),
                dict(self.row, ts="not a timestamp", session_ref="missing")]
        attrs = [self.attr(row) for row in rows]
        cov = self.D.evidence_coverage(rows, attrs, self.sessions)
        by_key = {(r["host"], r["period"]): r for r in cov["by_host_period"]}
        self.assertEqual(sum(r["rows"] for r in by_key.values()), 5)
        self.assertEqual(by_key["claude", "2026-09"]["anchor_attributed"], 1)
        self.assertEqual(by_key["codex", "2026-09"]["unattributed"], 1)
        self.assertEqual(by_key["unknown", "2026-09"]["evidence_hosts"], {"claude": 1})
        self.assertEqual(by_key["unknown", "unknown"]["unknown_route_evidence"], 1)
        self.assertEqual(cov["route_dates"], {"start": self.start,
                         "end": "2026-10-01T00:00:00Z", "unknown_timestamps": 1})
        self.assertEqual(cov["anchor_attributed_route_dates"]["end"], self.start)
        self.assertEqual(cov["transcript_adapters"]["codex"], "commands-only, opt-in")

    def test_unsupported_host_cannot_join_identical_digest_or_session(self):
        for host in ("codex", "other"):
            row = dict(self.row, host=host)
            rec = self.D.derive(row, self.sessions, self.index, self.times, [row], False)
            self.assertEqual(rec["attribution"]["method"], "none")
            self.assertEqual(rec["derived_state"], "unknown")
            self.assertEqual(rec["signals"], [])
            records, _, metrics, _ = score_adherence.build(
                [row], self.sessions, self.index, self.times)
            self.assertIsNone(records[0]["hint"])
            metric = next(m for m in metrics if m["id"] == "hint_before_route")
            self.assertEqual(metric["denominator"], 0)
            self.assertIsNone(metric["value"])

    def test_conflicting_session_reference_never_falls_back_to_another_session(self):
        self.assertEqual(self.attr(dict(self.row, session_ref="elsewhere"))["method"], "none")
        # Historical rows with no explicit reference retain exact anchor support.
        self.assertEqual(self.attr(dict(self.row, session_ref=None))["method"], "anchor-command")

    def test_no_heuristic_join_or_success_from_silence(self):
        row = dict(self.row, task_hash=None, session_ref=None,
                   session_id="2026-09-18-10", project="same-project")
        self.assertEqual(self.attr(row)["method"], "none")
        rec = self.D.derive(self.row, self.sessions, self.index, self.times, [self.row], False)
        self.assertEqual(rec["derived_state"], "unknown")
        self.assertEqual(rec["attribution"]["confidence"], "high")

    def test_singleton_anchor_requires_a_consistent_timestamp(self):
        for ref in (None, "session-a"):
            for stamp in (None, "invalid", "2026-01-18T10:00:00Z",
                          "2026-09-18T09:39:59Z", "2026-09-18T10:20:01Z"):
                with self.subTest(ref=ref, ts=stamp):
                    row = dict(self.row, session_ref=ref, ts=stamp)
                    rec = self.D.derive(row, self.sessions, self.index, self.times, [row], False)
                    self.assertEqual(rec["attribution"]["method"], "none")
                    self.assertIsNone(rec["attribution"]["session"])
                    self.assertEqual(rec["signals"], [])
                    self.assertEqual(rec["derived_state"], "unknown")
                    self.assertIsNone(score_adherence.hint_check(
                        row, self.attr(row), self.sessions, self.times))
        for stamp in ("2026-09-18T09:40:00Z", "2026-09-18T10:20:00Z"):
            attr = self.attr(dict(self.row, ts=stamp, session_ref=None))
            self.assertEqual(attr["method"], "anchor-command")
            self.assertEqual(attr["ts_drift_s"], 1200)

    def test_distant_repeat_cannot_reuse_the_only_surviving_anchor(self):
        january = "2026-01-18T10:00:00Z"
        command = self.index[self.row["task_hash"]][0][2]
        self.sessions["session-a"]["events"] = [self.event(january, command)]
        self.index, self.times = self.D.build_anchor_index(self.sessions)
        rows = [dict(self.row, session_ref=None, ts=stamp)
                for stamp in (january, self.start)]
        attrs = [self.attr(row) for row in rows]
        self.assertEqual([a["method"] for a in attrs], ["anchor-command", "none"])
        records, _, _, months = score_adherence.build(rows, self.sessions, self.index, self.times)
        self.assertEqual(months["2026-09"]["attributed"], 0)
        self.assertIsNone(records[1]["hint"])
        # When both executions survive, exact task + timestamp can select each one.
        self.sessions["session-b"] = {"host": "claude", "files": [],
                                      "events": [self.event(self.start, command)]}
        self.index, self.times = self.D.build_anchor_index(self.sessions)
        attrs = [self.attr(row) for row in rows]
        self.assertEqual([a["session"] for a in attrs], ["session-a", "session-b"])
        self.assertEqual([a["method"] for a in attrs], ["anchor-command+ts"] * 2)

    def test_reports_share_corrected_routes_without_crossing_execution_ids(self):
        rows = [dict(self.row, event="route", event_id=f"route-{i}",
                     ts=f"2026-0{i + 1}-18T10:00:00Z", session_ref=f"run-{i}")
                for i in range(3)]
        raw = rows + [
            {"event": "outcome", "ref": "route-0", "outcome": "shipped"},
            {"event": "outcome", "ref": "route-1", "outcome": "partial"},
            {"event": "reroute", "ref": "route-1", "user_correction": "Direct > retry @ L3"},
            {"event": "reclassify", "ref": "route-1", "tier": "L3"},
            {"event": "outcome", "ref": "missing", "outcome": "abandoned"},
        ]
        log = self.root / "corrections.jsonl"
        log.write_text("\n".join(map(json.dumps, raw)) + "\n")
        before = log.read_bytes()
        reports = []
        for module in (self.D, score_adherence):
            output = self.root / (module.__name__ + "-corrected.jsonl")
            args = ["--log", str(log), "--projects", str(self.root / "missing"), "--out", str(output)]
            if module is self.D:
                args.append("--no-git")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(args), 0)
            reports.append([json.loads(line) for line in output.read_text().splitlines()])
        self.assertEqual(log.read_bytes(), before)
        for report in reports:
            self.assertEqual(report[0]["log_rows"], 3)
            self.assertEqual(report[0]["non_route_rows_excluded"], 5)
            self.assertEqual([r["event_id"] for r in report[1:]], [r["event_id"] for r in rows])
            self.assertEqual([r["route_ts"] for r in report[1:]], [r["ts"] for r in rows])
        derived, adherence = reports[0][1:], reports[1][1:]
        self.assertEqual([r["self_reported_outcome"] for r in derived], ["shipped", "corrected", None])
        self.assertEqual([r["outcome"] for r in adherence], ["shipped", "corrected", None])
        self.assertEqual([r["route"]["tier"] for r in derived], ["L2", "L3", "L2"])
        self.assertEqual([r["tier"] for r in adherence], ["L2", "L3", "L2"])
        self.assertEqual([r["derived_state"] for r in derived], ["unknown"] * 3)
        collapsed, _ = self.D.load_route_log(log)
        self.assertEqual([r["session_ref"] for r in collapsed], [r["session_ref"] for r in rows])
        self.assertEqual(collapsed[1]["user_correction"], "Direct > retry @ L3")

    def test_collapse_failure_never_publishes_raw_outcomes(self):
        log = self.root / "log.jsonl"
        log.write_text(json.dumps(self.row) + "\n")
        output = self.root / "existing-report.jsonl"
        output.write_bytes(b"previous evidence\n")
        for module in (self.D, score_adherence):
            args = ["--log", str(log), "--out", str(output)]
            with patch.object(self.D, "load_route_log", side_effect=ValueError("cannot fold")), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(args), 1)
            self.assertEqual(output.read_bytes(), b"previous evidence\n")

    def test_reader_labels_claude_and_does_not_parse_codex_as_claude(self):
        project = self.root / "projects" / "fixture"
        project.mkdir(parents=True)
        codex = [
            {"type": "session_meta", "timestamp": self.start,
             "payload": {"id": "session-a", "session_id": "session-a", "forked_from_id": "parent"}},
            {"type": "response_item", "timestamp": self.start,
             "payload": {"type": "function_call", "name": "exec_command",
                         "arguments": json.dumps({"cmd": self.index[self.row["task_hash"]][0][2]})}},
        ]
        path = project / "fixture.jsonl"
        path.write_text("\n".join(map(json.dumps, codex)))
        self.assertEqual(self.D.load_sessions(project.parent), {})
        claude = {"type": "assistant", "timestamp": self.start, "sessionId": "session-a",
                  "uuid": "event-a", "message": {"content": [{"type": "tool_use", "name": "Bash",
                      "input": {"command": self.index[self.row["task_hash"]][0][2]}}]}}
        path.write_text(json.dumps(claude) + "\n")
        sessions = self.D.load_sessions(project.parent)
        self.assertEqual(sessions["session-a"]["host"], "claude")
        self.assertEqual(len(sessions["session-a"]["events"]), 1)

    def test_session_only_and_ambiguous_are_not_anchor_coverage(self):
        row = dict(self.row, task_hash=None)
        attr = self.attr(row)
        self.assertEqual((attr["method"], attr["window_kind"]), ("session_ref", "session"))
        cov = self.D.evidence_coverage([row], [attr], self.sessions)["by_host_period"][0]
        self.assertEqual((cov["anchor_attributed"], cov["session_ref_only"],
                          cov["unknown_route_evidence"]), (0, 1, 1))
        self.index[self.row["task_hash"]].append(("session-b", self.D.parse_ts(self.start), "anchor"))
        self.sessions['session-b'] = {'host': 'claude', 'events': [], 'files': []}
        attr = self.attr(dict(self.row, session_ref=None))
        self.assertEqual(attr["method"], "ambiguous")
        cov = self.D.evidence_coverage([self.row], [attr], self.sessions)["by_host_period"][0]
        self.assertEqual((cov["ambiguous"], cov["anchor_attributed"]), (1, 0))

    def test_anchor_window_and_gap_truncation_are_preserved(self):
        events = self.sessions["session-a"]["events"]
        events.append(self.event("2026-09-18T10:10:00Z", "cortex log-line 'Direct > fix @ L2' 'next task'"))
        events.append(self.event("2026-09-18T14:00:00Z"))
        self.index, self.times = self.D.build_anchor_index(self.sessions)
        attr = self.attr(self.row)
        self.assertEqual(attr["window_kind"], "route")
        self.assertEqual(self.D.iso(attr["end"]), "2026-09-18T10:10:00Z")
        row = dict(self.row, task_hash=self.D.task_hash("next task"), ts="2026-09-18T10:10:00Z")
        attr = self.attr(row)
        self.assertEqual(attr["window_kind"], "route-gap-truncated")
        self.assertEqual(attr["start"], attr["end"])

    def test_empty_and_invalid_dates_have_explicit_unknown_coverage(self):
        with self.assertRaisesRegex(ValueError, "one attribution per route"):
            self.D.evidence_coverage([self.row], [], {})
        cov = self.D.evidence_coverage([], [], {})
        self.assertEqual(cov["by_host_period"], [])
        self.assertEqual(cov["route_dates"], {"start": None, "end": None, "unknown_timestamps": 0})
        _, _, _, by_month = score_adherence.build([dict(self.row, ts="bad")], {}, {}, {})
        self.assertEqual(by_month["unknown"]["attributed"], 0)
        # Periods use UTC, including timezone crossings.
        row = dict(self.row, ts="2026-10-01T00:30:00+02:00")
        cov = self.D.evidence_coverage([row], [{"method": "none"}], {})
        self.assertEqual(cov["by_host_period"][0]["period"], "2026-09")

    def test_both_reports_emit_coverage_and_dynamic_warnings(self):
        log = self.root / "log.jsonl"
        log.write_text(json.dumps(dict(self.row, host="codex")) + "\n")
        for module in (self.D, score_adherence):
            output = self.root / (module.__name__ + ".jsonl")
            args = ["--log", str(log), "--projects", str(self.root / "missing"), "--out", str(output)]
            if module is self.D:
                args += ["--no-git"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(args), 0)
            header = json.loads(output.read_text().splitlines()[0])
            cov = header["evidence_coverage"]
            self.assertEqual(cov["by_host_period"][0]["host"], "codex")
            self.assertEqual(cov["by_host_period"][0]["unknown_route_evidence"], 1)
            self.assertEqual(cov["route_dates"]["start"], self.start)
            self.assertNotIn("July-August", output.read_text())
            before = output.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(module.main(args + ["--dry-run"]), 0)
            self.assertEqual(output.read_bytes(), before)
            self.assertIn("codex 2026-09 rows=1 anchor=0", stdout.getvalue())

    def test_unmeasurable_gate_is_incomplete_not_success(self):
        thresholds = self.root / "thresholds.json"
        thresholds.write_text(json.dumps({"floors": {"hint_before_route": {"min": 0}}}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = score_adherence.check_floors(score_adherence.transcript_metrics([]), thresholds)
        self.assertEqual(result, 1)
        self.assertIn("Gate incomplete", out.getvalue())
        self.assertIn("no coverage floor", out.getvalue())
        log = self.root / "log.jsonl"
        log.write_text(json.dumps(dict(self.row, host="codex")) + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(score_adherence.main([
                "--log", str(log), "--projects", str(self.root / "missing"),
                "--dry-run", "--check", "--thresholds", str(thresholds)]), 1)


if __name__ == "__main__":
    unittest.main()
