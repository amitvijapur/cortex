#!/usr/bin/env python3
"""Offline behavioural tests. No credentials or API calls required."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import cortex_jev as jev


def manifest():
    return {"schema_version": 1, "session_id": "host-session",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "capabilities": ["tool:edit", "agent:worker"], "candidates": [
                {"id": "direct", "system": "Direct", "pattern": "edit",
                 "description": "Small known edits", "requires": ["tool:edit"]},
                {"id": "worker", "system": "Host", "pattern": "delegate",
                 "agent": "worker", "description": "Bounded implementation work",
                 "requires": ["agent:worker"]}]}


def answer(choice, keys, confidence=0.95):
    return {"type": "choice", "choice": choice, "confidence": confidence,
            "probabilities": {key: 0.95 if key == choice else 0.05 / (len(keys) - 1)
                              for key in keys}}


def response():
    return {"model": jev.MODEL, "answers": {
        "classification": answer("build", jev.CLASSIFICATIONS),
        "workflow": answer("worker", ["worker", "direct", "abstain"])},
        "usage": {"input_tokens": 100, "output_tokens": 0}}


class AdviserTests(unittest.TestCase):
    def setUp(self):
        self.manifest = manifest()
        self.calls = []

    def transport(self, payload, key, timeout):
        self.calls.append(payload)
        return response()

    def run_adviser(self, **kwargs):
        options = dict(mode="advisory", session_id="host-session", api_key="fixture",
                       transport=self.transport)
        options.update(kwargs)
        return jev.advise("Implement the new feature", self.manifest, **options)

    def test_off_is_lazy(self):
        self.manifest = object()
        result = self.run_adviser(mode="off")
        self.assertEqual(result["status"], "off")
        self.assertEqual(result["cost_usd"], 0)
        self.assertEqual(self.calls, [])

    def test_advisory_full_candidate_independent_questions_and_cost(self):
        result = self.run_adviser()
        self.assertEqual(result["status"], "suggested")
        self.assertEqual(result["classification"], "build")
        self.assertEqual(result["candidate"], self.manifest["candidates"][1])
        self.assertFalse(result["fallback_required"])
        self.assertAlmostEqual(result["cost_usd"], 0.0000042)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(set(self.calls[0]["questions"]["workflow"]["criteria"]),
                         {"direct", "worker", "abstain"})
        self.assertNotIn("capabilities", self.calls[0])
        self.assertNotIn("task", result)

    def test_shadow_hides_all_signal_even_success_vs_abstention(self):
        good = self.run_adviser(mode="shadow")
        bad = self.run_adviser(mode="shadow", api_key="")
        self.assertEqual(jev.public_view(good), jev.public_view(bad))
        self.assertNotIn("worker", json.dumps(jev.public_view(good)))
        self.assertTrue(good["fallback_required"])
        self.assertEqual(good["candidate_id"], "worker")

    def test_override_never_calls_and_never_substitutes(self):
        result = self.run_adviser(explicit_candidate="direct")
        self.assertEqual(result["status"], "explicit")
        self.assertEqual(result["candidate_id"], "direct")
        invalid = self.run_adviser(explicit_candidate="not-available")
        self.assertEqual(invalid["fallback_reason"], "explicit_candidate_unavailable")
        self.assertIsNone(invalid["candidate_id"])
        self.assertEqual(self.calls, [])

    def test_missing_credentials(self):
        self.assertEqual(self.run_adviser(api_key="")["fallback_reason"], "missing_credentials")
        self.assertFalse(self.calls)

    def test_invalid_manifests_never_call(self):
        mutations = [lambda m: m.update(session_id="other"),
                     lambda m: m.update(generated_at=(datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()),
                     lambda m: m["candidates"][0].update(requires=["not-callable"]),
                     lambda m: m["candidates"][0].update(requires=[]),
                     lambda m: m["candidates"].append(copy.deepcopy(m["candidates"][0])),
                     lambda m: m.update(capabilities=[]),
                     lambda m: m.update(generated_at="2026-01-01T00:00:00"),
                     lambda m: m["candidates"][0].update(id="abstain")]
        for mutate in mutations:
            self.manifest = manifest()
            mutate(self.manifest)
            with self.subTest(manifest=self.manifest):
                self.assertEqual(self.run_adviser()["status"], "fallback")
        self.assertFalse(self.calls)

    def test_rejection_retains_known_usage_and_cost(self):
        for mutation in (
            lambda r: r["answers"]["workflow"].update(choice="unavailable"),
            lambda r: r["answers"]["workflow"].update(confidence=float("nan")),
            lambda r: r["answers"]["workflow"].update(confidence=10**400),
            lambda r: r["answers"]["workflow"]["probabilities"].update(worker=float("inf")),
            lambda r: r["answers"]["workflow"]["probabilities"].update(extra=0),
            lambda r: r["answers"]["workflow"].update(choice="direct"),
            lambda r: r["answers"]["workflow"]["probabilities"].update(worker=0.5),
            lambda r: r["answers"]["classification"].update(type="text"),
        ):
            data = response()
            mutation(data)
            result = self.run_adviser(transport=lambda *args: data)
            self.assertEqual(result["fallback_reason"], "invalid_response")
            self.assertEqual(result["usage"]["input_tokens"], 100)
            self.assertGreater(result["cost_usd"], 0)
            self.assertIsNone(result["candidate_id"])
            json.dumps(result, allow_nan=False)

    def test_abstention_and_uncertainty(self):
        data = response()
        data["answers"]["workflow"] = answer("abstain", ["worker", "direct", "abstain"])
        result = self.run_adviser(transport=lambda *args: data)
        self.assertEqual(result["fallback_reason"], "abstained")
        data = response()
        data["answers"]["classification"]["confidence"] = 0.2
        self.assertEqual(self.run_adviser(transport=lambda *args: data)["fallback_reason"], "low_confidence")

    def test_unknown_model_and_missing_usage_do_not_claim_free(self):
        data = response()
        data["model"] = "future-model"
        result = self.run_adviser(transport=lambda *args: data)
        self.assertEqual(result["fallback_reason"], "model_mismatch")
        self.assertIsNone(result["cost_usd"])
        data = response()
        del data["usage"]
        missing = self.run_adviser(transport=lambda *args: data)
        self.assertIsNone(missing["cost_usd"])
        self.assertEqual(missing["fallback_reason"], "invalid_response")

    def test_transport_errors_sanitized_unknown_cost(self):
        def broken(*args):
            raise RuntimeError("secret task or API token")
        result = self.run_adviser(transport=broken)
        self.assertEqual(result["fallback_reason"], "api_error")
        self.assertIsNone(result["cost_usd"])
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["request_count"], 1)

    def test_hostile_model_and_nonfinite_configuration(self):
        for model in ({"bad": "model"}, ["bad-model"], None, 7):
            data = response()
            data["model"] = model
            result = self.run_adviser(transport=lambda *args: data)
            self.assertEqual(result["fallback_reason"], "model_mismatch")
            self.assertIsNone(result["cost_usd"])
            json.dumps(result, allow_nan=False)
        for threshold in (float("nan"), float("inf"), 10**400):
            for mode in ("off", "advisory"):
                result = self.run_adviser(threshold=threshold, mode=mode)
                json.dumps(result, allow_nan=False)
        with tempfile.TemporaryDirectory() as tmp:
            for threshold in ("nan", "inf"):
                result = self.cli(Path(tmp).resolve(), "--mode", "advisory", "--threshold", threshold, "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["fallback_reason"], "invalid_configuration")

    def test_response_rechecks_manifest(self):
        def changing(*args):
            self.manifest["capabilities"] = ["tool:edit"]
            return response()
        result = self.run_adviser(transport=changing)
        self.assertEqual(result["fallback_reason"], "manifest_expired")

    def test_total_transport_timeout_includes_subprocess(self):
        original_run = subprocess.run
        def slow_child(*args, **kwargs):
            return original_run([sys.executable, "-c", "import time; time.sleep(5)"], **kwargs)
        started = time.monotonic()
        with patch.object(jev.subprocess, "run", side_effect=slow_child):
            result = self.run_adviser(transport=jev.http_transport, timeout=0.1)
        self.assertEqual(result["fallback_reason"], "timeout")
        self.assertLess(time.monotonic() - started, 1.0)

    def request_worker(self, opener):
        """Exercise the production worker's stdin and HTTP adapter without sockets."""
        request = {"payload": jev.build_payload("Implement a feature", self.manifest["candidates"]),
                   "key": "fixture-secret", "timeout": 0.7}
        with patch.object(jev.sys, "stdin", io.StringIO(json.dumps(request))), \
                patch.object(jev.urllib.request, "build_opener", return_value=opener) as factory:
            result = jev._request_worker()
        return result, request, factory

    def test_http_worker_request_contract_and_redirect_refusal(self):
        opener = Mock()
        body = opener.open.return_value.__enter__ = Mock()
        response_handle = body.return_value
        opener.open.return_value.__exit__ = Mock(return_value=False)
        response_handle.read.return_value = json.dumps(response()).encode()
        result, expected, factory = self.request_worker(opener)
        self.assertEqual(result, {"response": response()})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-secret")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(request.data), expected["payload"])
        self.assertEqual(opener.open.call_args.kwargs, {"timeout": 0.7})
        response_handle.read.assert_called_once_with(jev.MAX_RESPONSE_BYTES + 1)
        proxy, redirect = factory.call_args.args
        self.assertEqual(proxy.proxies, {})
        for code in (301, 302, 303, 307, 308):
            self.assertIsNone(redirect.redirect_request(request, None, code, "redirect", {},
                                                        "https://other.example/"))
        self.assertNotIn("fixture-secret", json.dumps(result))

    def test_http_worker_errors_are_sanitized(self):
        for code, reason in ((401, "api_error"), (429, "rate_limited"), (529, "api_error")):
            opener = Mock()
            opener.open.side_effect = urllib.error.HTTPError(
                "https://api.typesafe.ai/v1/systemone", code, "fixture-secret", {},
                io.BytesIO(b"private server response"))
            result, _, _ = self.request_worker(opener)
            self.assertEqual(result, {"error": reason})
            opener.open.side_effect.close()
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError("fixture-secret")
        result, _, _ = self.request_worker(opener)
        self.assertEqual(result, {"error": "network_error"})

    def test_http_worker_rejects_malformed_or_oversized_body(self):
        for body, reason in ((b"not-json fixture-secret", "invalid_response"),
                             (b"x" * (jev.MAX_RESPONSE_BYTES + 1), "response_too_large")):
            opener = Mock()
            opener.open.return_value.__enter__ = Mock()
            opener.open.return_value.__exit__ = Mock(return_value=False)
            opener.open.return_value.__enter__.return_value.read.return_value = body
            result, _, _ = self.request_worker(opener)
            self.assertEqual(result, {"error": reason})

    def test_http_transport_decodes_worker_envelopes(self):
        for envelope, reason in (({"response": response()}, None),
                                 ({"error": "rate_limited"}, "rate_limited"),
                                 ({"error": "api_error"}, "api_error"),
                                 ({"error": "private server message"}, "api_error")):
            child = subprocess.CompletedProcess([], 0, json.dumps(envelope), "")
            with patch.object(jev.subprocess, "run", return_value=child) as run:
                if reason:
                    with self.assertRaisesRegex(jev.TransportFailure, "^" + reason + "$"):
                        jev.http_transport({}, "fixture-secret", 0.7)
                else:
                    self.assertEqual(jev.http_transport({}, "fixture-secret", 0.7), response())
                self.assertNotIn("fixture-secret", " ".join(run.call_args.args[0]))
                self.assertEqual(json.loads(run.call_args.kwargs["input"])["key"], "fixture-secret")

    def test_experiment_append_rejects_production_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            production = home / "cortex-log.jsonl"
            production.write_text("production\n")
            record = self.run_adviser()
            jev.append_experiment(home, record)
            target = home / "experiments" / "jev" / (record["session_hash"] + ".jsonl")
            self.assertEqual(json.loads(target.read_text())["candidate_id"], "worker")
            target.unlink()
            target.symlink_to(production)
            with self.assertRaises(OSError):
                jev.append_experiment(home, record)
            target.unlink()
            os.link(production, target)
            with self.assertRaises(OSError):
                jev.append_experiment(home, record)
            self.assertEqual(production.read_text(), "production\n")

    def test_cli_off_does_not_read_manifest_or_touch_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "absent"
            result = self.cli(home, "--mode", "off", "--manifest", "/nonexistent", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "off")
            self.assertFalse(home.exists())

    def cli(self, home, *args):
        env = dict(os.environ, CORTEX_HOME=str(home), TYPESAFE_API_KEY="",
                   CORTEX_SESSION_ID="host-session", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "bin" / "cortex"),
                               "advise", "Implement the new feature", *args],
                              text=True, capture_output=True, env=env, timeout=5)

    def test_cli_separate_log_and_hint_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            production = home / "cortex-log.jsonl"
            production.write_text(json.dumps({"task": "old", "class": "build", "system": "Direct",
                "pattern": "edits", "tier": "L2"}) + "\n")
            before = production.read_bytes()
            mp = home / "manifest.json"
            mp.write_text(json.dumps(self.manifest))
            result = self.cli(home, "--mode", "shadow", "--manifest", str(mp), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "shadow")
            records = list((home / "experiments" / "jev").glob("*.jsonl"))
            self.assertEqual(len(records), 1)
            self.assertEqual(json.loads(records[0].read_text())["fallback_reason"], "missing_credentials")
            self.assertEqual(production.read_bytes(), before)
            result = subprocess.run([sys.executable, str(ROOT / "bin" / "cortex"), "hint", "new", "--class", "build"],
                env=dict(os.environ, CORTEX_HOME=str(home), CORTEX_JEV_MODE="advisory", TYPESAFE_API_KEY="never-send"),
                text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Direct > edits @ L2", result.stdout)
            self.assertEqual(production.read_bytes(), before)
            self.assertEqual(len(records[0].read_text().splitlines()), 1)

    def test_cli_failed_logging_suppresses_advice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            (home / "experiments").write_text("not a directory")
            mp = home / "manifest.json"
            mp.write_text(json.dumps(self.manifest))
            result = self.cli(home, "--mode", "advisory", "--manifest", str(mp),
                              "--explicit-candidate", "direct", "--json")
            record = json.loads(result.stdout)
            self.assertEqual(record["fallback_reason"], "experiment_log_failed")
            self.assertIsNone(record["candidate_id"])

    def test_successful_cli_shadow_persists_without_exposing_candidate(self):
        import contextlib
        import io
        loader = importlib.machinery.SourceFileLoader("cortex_jev_test_cli", str(ROOT / "bin" / "cortex"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            mp = home / "manifest.json"
            mp.write_text(json.dumps(self.manifest))
            args = cli.build_parser().parse_args(["advise", "Implement a feature", "--mode", "shadow",
                                                 "--manifest", str(mp), "--json"])
            output = io.StringIO()
            with patch.object(cli, "CLAUDE_DIR", home), patch.object(jev, "http_transport", self.transport), \
                    patch.dict(os.environ, {"TYPESAFE_API_KEY": "fixture", "CORTEX_SESSION_ID": "host-session"}), \
                    contextlib.redirect_stdout(output):
                cli.cmd_advise(args)
            self.assertNotIn("worker", output.getvalue())
            record = json.loads(next((home / "experiments" / "jev").glob("*.jsonl")).read_text())
            self.assertEqual(record["candidate_id"], "worker")
            self.assertEqual(record["request_count"], 1)
            self.assertFalse((home / "cortex-log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
