#!/usr/bin/env python3
"""Offline Jev replay integrity tests. No credentials, models or personal logs."""
import contextlib
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jev_eval as ev


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.data = ev.read_json(ev.DEFAULT_DATASET)
        self.candidates = self.data["candidates"]

    def run_fixture(self, **kwargs):
        with patch("subprocess.run", side_effect=AssertionError("no external calls")):
            return ev.evaluate(self.data, self.candidates, **kwargs)

    def manifest(self):
        return {"schema_version": 1, "session_id": "test-host",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "capabilities": ["tool:exec", "agent:worker", "tool:web"],
                "candidates": self.candidates}

    def reviewed(self):
        for case in self.data["cases"]:
            case["labels"].update(reviewed=True, reviewer="synthetic-test-reviewer",
                                  reviewed_at="2026-09-20", provenance="test only")

    def runs(self, report):
        runs = []
        for row in report["rows"]:
            for arm in ev.ARMS:
                runs.append({"case_id": row["id"], "arm": arm,
                             "context_hash": row["context_hash"],
                             "candidates_hash": report["inputs"]["candidates_hash"],
                             "advice_hash": row["advice_hash"], "synthetic": False,
                             "model": "test-session-model", "protocol_hash": "test-protocol",
                             "candidate_id": "direct", "classification": "quickfix",
                             "attempts": [{"cost_usd": .02, "latency_ms": 10},
                                          {"cost_usd": .03, "latency_ms": 20}],
                             "end_to_end_ms": 40, "reroutes": 1})
        return {"runs": runs}

    def test_fixture_is_not_evidence_of_quality_or_savings(self):
        report = self.run_fixture()
        self.assertEqual(report["execution"], "synthetic_plumbing_only")
        summary = report["summary"]
        self.assertFalse(summary["quality_ready"])
        self.assertIsNone(summary["quality"])
        self.assertEqual(summary["coverage"], .5)
        self.assertEqual(summary["jev_only"]["request_count"], 5)
        self.assertIsNone(summary["jev_only"]["cost_usd"])
        self.assertEqual(summary["jev_only"]["unknown_cost_attempts"], 1)
        self.assertIsNone(summary["existing_calls_avoided"])
        self.assertTrue(summary["recommendation"].startswith("keep_off"))
        for arm in ev.ARMS:
            self.assertIsNone(summary["arms"][arm]["workflow_accuracy"])
            self.assertIsNone(summary["arms"][arm]["total_cost_usd"])

    def test_off_is_zero_adviser_requests_and_zero_added_cost(self):
        summary = self.run_fixture(mode="off")["summary"]
        self.assertEqual(summary["jev_only"]["request_count"], 0)
        self.assertEqual(summary["jev_only"]["cost_usd"], 0)

    def test_future_correction_and_outcome_do_not_leak(self):
        case = copy.deepcopy(self.data["cases"][0])
        case["history_prefix"] = 2
        before, entries, _ = ev.hint_context(case, self.data["history"])
        self.assertEqual(entries[0]["tier"], "L1")
        self.assertNotIn("outcome", entries[0])
        case["history_prefix"] = 5
        after, entries, _ = ev.hint_context(case, self.data["history"])
        self.assertEqual(entries[0]["tier"], "L2")
        self.assertEqual(entries[0]["outcome"], "shipped")
        self.assertNotEqual(before, after)

    def test_actual_hint_dedup_ignores_agent_and_orders_latest(self):
        history = [dict(event_id=f"r{i}", task=f"prior {i}", **fields) for i, fields in enumerate([
            {"class": "build", "system": "Direct", "pattern": "edits", "tier": "L1", "agent": "a"},
            {"class": "build", "system": "OMC", "pattern": "team", "tier": "L3"},
            {"class": "build", "system": "Direct", "pattern": "edits", "tier": "L1", "agent": "b"},
            {"class": "research", "system": "Other", "pattern": "research", "tier": "L2"},
        ])]
        context, _, _ = ev.hint_context({"task": "new task", "query_class": "build", "history_prefix": 4}, history)
        self.assertIn("2 most recent distinct routes", context["hint"])
        self.assertIn("prior 2", context["hint"])
        self.assertNotIn("prior 0", context["hint"])
        self.assertNotIn("Other >", context["hint"])
        self.assertLess(context["hint"].index("Direct >"), context["hint"].index("OMC >"))

    def test_classifier_cannot_see_gold_or_session_class(self):
        case = self.data["cases"][0]
        case.update(query_class="secret_gold", historical_candidate_id="secret_route")
        self.assertEqual(ev.classifier_input(case), case["task"])
        self.assertNotIn("secret", ev.classifier_input(case))

    def test_repeated_groups_and_identical_tasks_cannot_cross_splits(self):
        self.data["cases"][2]["group"] = self.data["cases"][0]["group"]
        with self.assertRaisesRegex(ValueError, "group crosses"):
            self.run_fixture()
        self.data = ev.read_json(ev.DEFAULT_DATASET)
        self.data["cases"][2]["task"] = self.data["cases"][0]["task"].upper()
        with self.assertRaisesRegex(ValueError, "identical tasks"):
            self.run_fixture()

    def test_target_cannot_be_in_its_own_history(self):
        self.data["cases"][0]["target_event_index"] = 1
        with self.assertRaisesRegex(ValueError, "target event"):
            self.run_fixture()

    def test_accounting_retains_retries_and_unknown_failures(self):
        attempts = [{"cost_usd": .01, "latency_ms": 1, "error": "rate_limited"},
                    {"cost_usd": .02, "latency_ms": 2}]
        result = ev.accounting(attempts)
        self.assertEqual(result["cost_usd"], .03)
        self.assertEqual(result["attempt_count"], 2)
        attempts.append({"cost_usd": None, "latency_ms": 3, "error": "timeout"})
        result = ev.accounting(attempts)
        self.assertIsNone(result["cost_usd"])
        self.assertEqual(result["known_cost_usd"], .03)
        self.assertEqual(result["latency_ms"], 6)
        with self.assertRaisesRegex(ValueError, "count"):
            ev.adviser_accounting({"attempts": attempts, "request_count": 2})

    def test_malformed_numeric_costs_are_unknown_not_zero(self):
        for value in (-1, float("inf"), float("nan"), 10**400, True, "free"):
            result = ev.accounting([{"cost_usd": value, "latency_ms": 1}])
            self.assertIsNone(result["cost_usd"])
            self.assertEqual(result["unknown_cost_attempts"], 1)

    def test_missing_baseline_withholds_quality_even_with_reviewed_labels(self):
        self.reviewed()
        report = self.run_fixture()
        report["execution"] = "live"
        for row in report["rows"]:
            row["jev"]["model"] = row["jev"]["returned_model"] = "jev-1.13.0"
            row["jev"].pop("synthetic", None)
        replay = self.run_fixture(records=report)
        self.assertFalse(replay["summary"]["quality_ready"])

    def test_real_provenance_not_enough_without_real_response(self):
        self.reviewed()
        report = self.run_fixture()
        report["execution"] = "live"
        for row in report["rows"]:
            row["jev"]["model"] = "jev-1.13.0"
            row["jev"].pop("synthetic", None)
            row["advice_hash"] = ev.advice_hash(row["jev"])
        sessions = self.runs(report)
        replay = self.run_fixture(records=report, session_document=sessions)
        self.assertFalse(replay["summary"]["quality_ready"])

    def test_session_cost_counts_fallback_once_and_adviser_once(self):
        report = self.run_fixture()
        replay = self.run_fixture(records=report, session_document=self.runs(report))
        arms = replay["summary"]["arms"]
        self.assertAlmostEqual(arms["baseline"]["total_cost_usd"], .3)
        self.assertEqual(arms["baseline"]["request_count"], 12)
        self.assertEqual(arms["shadow"]["request_count"], 17)
        self.assertIsNone(arms["shadow"]["total_cost_usd"])
        self.assertEqual(arms["advisory"]["reroutes"], 6)
        self.assertEqual(arms["advisory"]["end_to_end_latency_ms"]["p95"], 40)
        self.assertEqual(replay["summary"]["collection_totals"]["request_count"], 41)
        self.assertEqual(arms["advisory"]["explicit_choice_violations"], 1)

    def test_paired_cost_comparison_excludes_unequal_tuning_runs(self):
        report = self.run_fixture()
        runs = self.runs(report)
        runs["runs"] = [r for r in runs["runs"] if not (r["case_id"] == "typo" and r["arm"] == "advisory")]
        replay = self.run_fixture(records=report, session_document=runs)
        paired = replay["summary"]["paired_heldout"]
        self.assertEqual(paired["denominator"], 4)
        self.assertEqual({m["session_cases"] for m in paired["arms"].values()}, {4})
        self.assertEqual(replay["summary"]["arms"]["advisory"]["session_cases"], 5)
        self.assertAlmostEqual(paired["arms"]["baseline"]["total_cost_usd"], .2)

    def test_synthetic_record_cannot_be_relabelled_live(self):
        report = self.run_fixture()
        report["execution"] = "live"
        with self.assertRaisesRegex(ValueError, "synthetic adviser"):
            self.run_fixture(records=report)

    def test_structured_override_and_capabilities_are_bound_to_context(self):
        report = self.run_fixture()
        self.assertEqual(report["rows"][-1]["context"]["explicit_candidate"], "team")
        self.data["capabilities"].append("tool:new")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.run_fixture(records=report)

    def test_session_mismatch_or_shadow_advice_leak_refused(self):
        report = self.run_fixture()
        for field, value in (("context_hash", "bad"), ("candidates_hash", "bad"),
                             ("synthetic", True), ("advice_visible", True)):
            runs = self.runs(report)
            runs["runs"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_fixture(records=report, session_document=runs)
        runs = self.runs(report)
        runs["runs"][1]["model"] = "different-model"
        with self.assertRaisesRegex(ValueError, "model/protocol"):
            self.run_fixture(records=report, session_document=runs)

    def test_replay_fingerprint_changes_invalidate_records(self):
        report = self.run_fixture()
        self.data["cases"][0]["task"] += " Changed."
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.run_fixture(records=report)

    def test_unavailable_suggestion_counted(self):
        self.data["cases"][0]["fixture"]["candidate_id"] = "missing"
        self.assertEqual(self.run_fixture()["summary"]["unavailable_candidate_errors"], 1)

    def test_reviewed_abstention_is_valid_but_missing_candidate_is_not(self):
        self.reviewed()
        report = self.run_fixture()
        runs = self.runs(report)
        for run in runs["runs"]:
            if run["case_id"] == "ambiguous":
                run.update(candidate_id="abstain", classification="abstain")
        replay = self.run_fixture(records=report, session_document=runs)
        self.assertEqual(replay["summary"]["arms"]["baseline"]["session_abstentions"], 1)
        self.assertEqual(replay["summary"]["arms"]["baseline"]["unavailable_candidate_errors"], 0)
        runs["runs"][0]["candidate_id"] = None
        replay = self.run_fixture(records=report, session_document=runs)
        self.assertEqual(replay["summary"]["arms"]["baseline"]["unavailable_candidate_errors"], 1)

    def test_live_requires_external_session_and_bounded_calls(self):
        manifest = self.manifest()
        for kwargs in ({"session_id": None, "max_calls": 6},
                       {"session_id": "wrong-host", "max_calls": 6},
                       {"session_id": "test-host", "max_calls": 5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_fixture(live=True, manifest=manifest, **kwargs)

    def test_model_alias_and_invalid_threshold_refused(self):
        for kwargs in ({"model": "jev-latest"}, {"threshold": float("nan")}, {"threshold": 10**400}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_fixture(**kwargs)

    def test_live_path_calls_runtime_with_only_task_and_explicit_override(self):
        runtime = ev.load_module("jev_eval_test_runtime", ev.REPO / "bin/cortex_jev.py")
        captured = []
        def fake_advise(task, manifest, **kwargs):
            captured.append((task, kwargs))
            return {"status": "fallback", "fallback_reason": "missing_credentials",
                    "request_count": 0, "cost_usd": 0, "latency_ms": 0}
        with patch.object(runtime, "advise", side_effect=fake_advise), patch.object(ev, "load_module", return_value=runtime):
            report = self.run_fixture(live=True, manifest=self.manifest(), session_id="test-host", max_calls=6)
        self.assertEqual(len(captured), 6)
        self.assertEqual(captured[-1][1]["explicit_candidate"], "team")
        self.assertEqual(captured[0][0], self.data["cases"][0]["task"])
        self.assertFalse(report["summary"]["quality_ready"])

    def test_report_never_overwrites_or_appends_production_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "cortex-log.jsonl"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ev.main(["--out", str(log)]), 2)
            self.assertFalse(log.exists())
            log.write_text("existing immutable event\n")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ev.main(["--out", str(log)]), 2)
            self.assertEqual(log.read_text(), "existing immutable event\n")
            out = Path(tmp) / "pilot.json"
            with patch("subprocess.run", side_effect=AssertionError("no process")):
                self.assertEqual(ev.main(["--out", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text())["execution"], "synthetic_plumbing_only")
            self.assertEqual(log.read_text(), "existing immutable event\n")

    def test_cli_rejects_conflicting_host_session_before_live_request(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "actual-host"}, clear=True), \
                patch.object(ev, "evaluate", side_effect=AssertionError("must not run")), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ev.main(["--live", "--session-id", "another-host", "--max-calls", "6"]), 2)


if __name__ == "__main__":
    unittest.main()
