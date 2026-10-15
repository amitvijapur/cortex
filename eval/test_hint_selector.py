#!/usr/bin/env python3
"""Production selector, actual CLI, and raw-prefix benchmark regression tests.

Run: PYTHONDONTWRITEBYTECODE=1 python3 eval/test_hint_selector.py
All CLI runs use temporary CORTEX_HOME directories. No model calls or live writes.
"""
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hint_arms as arms

CLI = arms._cli


def route(identifier, pattern="alpha", tier="L2", classification="build", task="cache repair"):
    return {"event": "route", "event_id": identifier, "task": task,
            "system": "Direct", "pattern": pattern, "tier": tier,
            "class": classification, "ts": "2026-09-01T00:00:00Z"}


class HintSelectorTests(unittest.TestCase):
    def test_low_route_confidence_warning_broadens_without_adding_a_gate(self):
        with patch("sys.stderr", new_callable=io.StringIO) as warning:
            CLI.flag_low_confidence({"route_confidence": "low"})
        self.assertIn("remove optional similarity/tier filters or increase --top",
                      warning.getvalue())
        self.assertNotIn("--min-similarity 0.05", warning.getvalue())

    def run_cli(self, rows, *args, script=None):
        with tempfile.TemporaryDirectory(prefix="cortex-hint-") as directory:
            log = Path(directory) / "cortex-log.jsonl"
            contents = "".join(json.dumps(row) + "\n" for row in rows)
            log.write_text(contents)
            env = dict(os.environ, CORTEX_HOME=directory, PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run(
                [sys.executable, str(script or arms.REPO / "bin" / "cortex"), *args],
                capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text(), contents)
            return result.stdout

    def assert_equivalent(self, rows, task="cache repair", **kwargs):
        entries = CLI.collapse(rows)
        before = copy.deepcopy(entries)
        pool, selected, reason = CLI.select_hint(entries, task, **kwargs)
        self.assertEqual(entries, before, "selector must not mutate its inputs")
        args = ["hint", task]
        for key, flag in (("classification", "--class"), ("tier", "--tier"),
                          ("top", "--top"), ("min_similarity", "--min-similarity")):
            if key in kwargs and kwargs[key] is not None:
                args.extend([flag, str(kwargs[key])])
        output = self.run_cli(rows, *args)
        actual = re.findall(r"^  \[sim [^\]]+\] \[[^\]]+\] (.+)$", output, re.M)
        expected = [f"{e['system']} > {e['pattern']} @ {e['tier']}" for e in selected]
        self.assertEqual(actual, expected, output)
        actual_tasks = re.findall(r"^         task: (.*)$", output, re.M)
        self.assertEqual(actual_tasks, [e["task"][:80] for e in selected])
        if selected:
            self.assertIn(f"(of {len(pool)} entries)", output)
        return selected, reason, output

    def test_distinct_recency_ignores_agent_similarity_outcome_and_timestamp(self):
        rows = [route("a", "old"), route("b", "repeat"),
                route("c", "middle"), route("d", "repeat", task="unrelated words")]
        rows[1].update(agent="first", outcome="shipped", ts="2099-01-01")
        rows[-1].update(agent="second", outcome="abandoned", ts="2000-01-01")
        selected, _, output = self.assert_equivalent(rows, classification="build", top=3)
        self.assertEqual([e["event_id"] for e in selected], ["d", "c", "a"])
        self.assertIn("[sim 0.00] [abandoned] Direct > repeat @ L2", output)
        self.assertEqual(arms.arm_production({"task": "cache repair", "class": "build"},
                                            CLI.collapse(rows)), selected)

    def test_filters_precede_distinct_and_tier_is_part_of_identity(self):
        rows = [route("a"), route("b", tier="L3"),
                route("c", classification="debug"), route("d", "other")]
        for options, ids in (({}, ["d", "c", "b"]),
                             ({"classification": "build"}, ["d", "b", "a"]),
                             ({"tier": "L2"}, ["d", "c"]),
                             ({"classification": "build", "tier": "L2"}, ["d", "a"])):
            with self.subTest(options=options):
                selected, _, _ = self.assert_equivalent(rows, **options)
                self.assertEqual([e["event_id"] for e in selected], ids)

    def test_similarity_gate_before_dedup_inclusive_not_ranking(self):
        rows = [route("a"), route("b", task="unrelated words"),
                route("c", "other", task="cache")]
        selected, _, _ = self.assert_equivalent(rows, min_similarity=0.5)
        self.assertEqual([e["event_id"] for e in selected], ["c", "a"])
        selected, _, _ = self.assert_equivalent(rows, min_similarity=0.0)
        self.assertEqual([e["event_id"] for e in selected], ["c", "b"])

    def test_empty_cases_and_messages(self):
        cases = [([], {}, "empty", "cortex log is empty"),
                 ([route("a")], {"classification": "debug"}, "filter",
                  "no past entries match filter (class=debug)"),
                 ([route("a")], {"min_similarity": 1.1}, "similarity",
                  "no past routes above similarity 1.1")]
        for rows, options, reason, message in cases:
            with self.subTest(reason=reason):
                selected, actual_reason, output = self.assert_equivalent(rows, **options)
                self.assertEqual(selected, [])
                self.assertEqual(actual_reason, reason)
                self.assertIn(message, output)

    def test_empty_tokens_and_historical_nonpositive_top(self):
        for top in (-1, 0, 1, 5):
            selected, _, _ = self.assert_equivalent([route("a"), route("b", "other")],
                                                    task="a", top=top)
            self.assertEqual(len(selected), 1 if top <= 1 else 2)
        selected, _, _ = self.assert_equivalent([route("a", task="")],
                                                task="", min_similarity=0)
        self.assertEqual(len(selected), 1)

    def test_current_corrections_match_cli(self):
        rows = [route("a"), route("b", "other"),
                {"event": "reclassify", "ref": "a", "tier": "L3"},
                {"event": "outcome", "ref": "a", "outcome": "partial"}]
        selected, _, output = self.assert_equivalent(rows, tier="L3")
        self.assertEqual([e["event_id"] for e in selected], ["a"])
        self.assertIn("[partial] Direct > alpha @ L3", output)

    def test_historical_arms_remain_separate(self):
        pool = [route("a", "old"), *[route(str(i), "repeat") for i in range(6)]]
        query = route("q", task="unrelated words")
        self.assertEqual(len(arms.arm_recency(query, pool)), 5)
        self.assertEqual(len(arms.arm_production(query, pool)), 2)
        self.assertEqual(arms.arm_jaccard(query, pool), [])
        self.assertIn(arms.arm_production, arms.ARMS.values())
        self.assertIn(arms.arm_jaccard, arms.ARMS.values())
        self.assertFalse(any("shipped" in name for name in arms.ARMS))

    def test_default_top_five_and_legacy_prefix(self):
        rows = [route(str(i), f"route{i}") for i in range(7)]
        for row in rows:
            row.pop("event")
            row.pop("event_id")
        selected, _, _ = self.assert_equivalent(rows, classification="build")
        self.assertEqual([e["pattern"] for e in selected],
                         [f"route{i}" for i in range(6, 1, -1)])
        cases = list(arms.replay_cases(rows))
        self.assertEqual(len(cases), 4)
        self.assertEqual(cases[0][0], rows[3])
        self.assertEqual([e["pattern"] for e in cases[0][1]],
                         ["route0", "route1", "route2"])

    def test_raw_prefix_blocks_future_corrections_including_backdated_events(self):
        prior = route("a")
        rows = [prior, route("b", "beta"), route("c", "gamma"), route("q1"),
                {"event": "reclassify", "ref": "a", "tier": "L4", "ts": "1900"},
                {"event": "outcome", "ref": "a", "outcome": "shipped", "ts": "1900",
                 "task": "this correction is not a query"}, route("q2", "delta")]
        before = copy.deepcopy(rows)
        cases = list(arms.replay_cases(rows))
        self.assertEqual([q["event_id"] for q, _ in cases], ["q1", "q2"])
        first, second = cases[0][1][0], cases[1][1][0]
        self.assertEqual(first["tier"], "L2")
        self.assertNotIn("outcome", first)
        self.assertEqual(second["tier"], "L4")
        self.assertEqual(second["outcome"], "shipped")
        self.assertEqual(cases[0], list(arms.replay_cases(rows[:4]))[0])
        future = [{"event": "reroute", "ref": "a", "user_correction": "future"},
                  {"event": "reclassify", "ref": "q1", "tier": "L1"}]
        self.assertEqual(cases, list(arms.replay_cases(rows + future)))
        self.assertEqual(rows, before)
        for q, pool in cases:
            cutoff = rows.index(q)
            selected, _, _ = self.assert_equivalent(rows[:cutoff], task=q["task"],
                                                    classification=q["class"])
            self.assertEqual(arms.arm_production(q, pool), selected)

    def test_production_never_filters_on_query_tier_or_agent(self):
        pool = [route("a")]
        query = route("q", tier="L4")
        query["agent"] = "unknown"
        self.assertEqual(arms.arm_production(query, pool), pool)
        with patch.object(CLI, "select_hint", wraps=CLI.select_hint) as selector:
            arms.arm_production(query, pool)
            selector.assert_called_once_with(pool, query["task"], classification="build",
                                             top=arms.TOP_N)

    def test_benchmark_main_empty_and_zero_findable(self):
        for rows in ([], [route(str(i), f"unique{i}") for i in range(5)]):
            output = self.run_cli(rows, script=arms.REPO / "eval" / "hint_arms.py")
            if rows:
                self.assertIn("production, distinct class", output)
                self.assertIn("findable: 0", output)
            else:
                self.assertIn("No eligible queries", output)


if __name__ == "__main__":
    unittest.main()
