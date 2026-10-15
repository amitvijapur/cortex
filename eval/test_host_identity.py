#!/usr/bin/env python3
"""Host/session provenance and real CLI regressions, with disposable state only.

Run: PYTHONDONTWRITEBYTECODE=1 python3 eval/test_host_identity.py
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


CLI = Path(__file__).resolve().parents[1] / "bin" / "cortex"
IDENTITY_KEYS = (
    "CORTEX_HOST", "CORTEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
)
PPID_REF = "ppid_" + hashlib.sha1(b"123|Tue Sep 29 10:00:00 2026").hexdigest()[:10]


def load_cli():
    loader = importlib.machinery.SourceFileLoader("cortex_host_test", str(CLI))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.cli = load_cli()

    def test_environment_matrix(self):
        # name, environment, host, host source, session ref, session source
        cases = [
            ("bare shell", {}, "unknown", None, PPID_REF, "ppid"),
            ("codex thread", {"CODEX_THREAD_ID": "thread"},
             "codex", "CODEX_THREAD_ID", "thread", "CODEX_THREAD_ID"),
            ("codex distinct runtime id", {"CODEX_THREAD_ID": "thread",
                                           "CODEX_SESSION_ID": "runtime"},
             "codex", "CODEX_THREAD_ID", "thread", "CODEX_THREAD_ID"),
            ("codex runtime only", {"CODEX_SESSION_ID": "runtime"},
             "codex", "CODEX_SESSION_ID", PPID_REF, "ppid"),
            ("claude canonical", {"CLAUDE_CODE_SESSION_ID": "claude"},
             "claude", "CLAUDE_CODE_SESSION_ID", "claude", "CLAUDE_CODE_SESSION_ID"),
            ("claude alias", {"CLAUDE_SESSION_ID": "legacy"},
             "claude", "CLAUDE_SESSION_ID", "legacy", "CLAUDE_SESSION_ID"),
            ("claude precedence", {"CLAUDE_CODE_SESSION_ID": "canonical",
                                   "CLAUDE_SESSION_ID": "legacy"},
             "claude", "CLAUDE_CODE_SESSION_ID", "canonical", "CLAUDE_CODE_SESSION_ID"),
            ("mixed native hosts", {"CLAUDE_CODE_SESSION_ID": "claude",
                                    "CODEX_THREAD_ID": "thread"},
             "unknown", "conflicting_env", None, None),
            ("equal ids still conflict", {"CLAUDE_SESSION_ID": "same",
                                         "CODEX_THREAD_ID": "same"},
             "unknown", "conflicting_env", None, None),
            ("runtime evidence conflicts", {"CLAUDE_SESSION_ID": "claude",
                                            "CODEX_SESSION_ID": "runtime"},
             "unknown", "conflicting_env", None, None),
            ("session override alone", {"CORTEX_SESSION_ID": "scope"},
             "unknown", None, "scope", "CORTEX_SESSION_ID"),
            ("session override codex", {"CORTEX_SESSION_ID": "scope",
                                       "CODEX_THREAD_ID": "thread"},
             "codex", "CODEX_THREAD_ID", "scope", "CORTEX_SESSION_ID"),
            ("session override claude", {"CORTEX_SESSION_ID": "scope",
                                        "CLAUDE_CODE_SESSION_ID": "claude"},
             "claude", "CLAUDE_CODE_SESSION_ID", "scope", "CORTEX_SESSION_ID"),
            ("session override does not resolve host", {"CORTEX_SESSION_ID": "scope",
              "CLAUDE_SESSION_ID": "claude", "CODEX_THREAD_ID": "thread"},
             "unknown", "conflicting_env", "scope", "CORTEX_SESSION_ID"),
            ("explicit codex resolves conflict", {"CORTEX_HOST": " CoDeX ",
              "CLAUDE_SESSION_ID": "claude", "CODEX_THREAD_ID": "thread"},
             "codex", "CORTEX_HOST", "thread", "CODEX_THREAD_ID"),
            ("explicit claude resolves conflict", {"CORTEX_HOST": "claude",
              "CLAUDE_SESSION_ID": "claude", "CODEX_THREAD_ID": "thread"},
             "claude", "CORTEX_HOST", "claude", "CLAUDE_SESSION_ID"),
            ("explicit host never borrows another host id", {"CORTEX_HOST": "codex",
              "CLAUDE_CODE_SESSION_ID": "claude"},
             "codex", "CORTEX_HOST", PPID_REF, "ppid"),
            ("other host", {"CORTEX_HOST": "cursor", "CODEX_THREAD_ID": "thread"},
             "cursor", "CORTEX_HOST", PPID_REF, "ppid"),
            ("explicit unknown", {"CORTEX_HOST": "unknown", "CODEX_THREAD_ID": "thread"},
             "unknown", "CORTEX_HOST", PPID_REF, "ppid"),
            ("both overrides", {"CORTEX_HOST": "cursor", "CORTEX_SESSION_ID": " scope ",
              "CLAUDE_CODE_SESSION_ID": "claude", "CODEX_THREAD_ID": "thread"},
             "cursor", "CORTEX_HOST", "scope", "CORTEX_SESSION_ID"),
            ("whitespace ignored", dict.fromkeys(IDENTITY_KEYS, " \t\n"),
             "unknown", None, PPID_REF, "ppid"),
            ("whitespace override ignored", {"CORTEX_SESSION_ID": "  ",
              "CORTEX_HOST": "\t", "CODEX_THREAD_ID": " thread \n"},
             "codex", "CODEX_THREAD_ID", "thread", "CODEX_THREAD_ID"),
            ("blank claude primary", {"CLAUDE_CODE_SESSION_ID": " ",
                                      "CLAUDE_SESSION_ID": " legacy "},
             "claude", "CLAUDE_SESSION_ID", "legacy", "CLAUDE_SESSION_ID"),
            ("blank codex thread", {"CODEX_THREAD_ID": " ", "CODEX_SESSION_ID": "runtime"},
             "codex", "CODEX_SESSION_ID", PPID_REF, "ppid"),
            ("model is not host", {"CORTEX_MODEL": "codex", "CLAUDE_MODEL": "claude",
                                   "ANTHROPIC_MODEL": "claude"},
             "unknown", None, PPID_REF, "ppid"),
        ]
        for name, env, host, host_source, session, session_source in cases:
            with self.subTest(name=name), mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(self.cli.os, "getppid", return_value=123), \
                    mock.patch.object(self.cli.subprocess, "run", return_value=
                                      subprocess.CompletedProcess([], 0, "Tue Sep 29 10:00:00 2026\n")) as ps:
                self.cli._AGENT_IDENTITY = None
                self.assertEqual(self.cli.agent_identity(), {
                    "host": host, "host_source": host_source,
                    "session_ref": session, "session_ref_source": session_source,
                })
                self.assertEqual(self.cli.agent_session_id(), session)
                self.assertEqual(ps.call_count, int(session_source == "ppid"))

    def test_ppid_failure_is_unknown(self):
        failures = [OSError("ps unavailable"), subprocess.TimeoutExpired("ps", 2),
                    subprocess.CompletedProcess([], 0, " \n"),
                    subprocess.CompletedProcess([], 1, "untrusted output")]
        for result in failures:
            with self.subTest(result=result), mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(self.cli.subprocess, "run") as ps:
                ps.side_effect = result if isinstance(result, Exception) else None
                ps.return_value = result
                self.cli._AGENT_IDENTITY = None
                self.assertEqual(self.cli.agent_identity(), {
                    "host": "unknown", "host_source": None,
                    "session_ref": None, "session_ref_source": None,
                })

    def test_identity_is_cached_as_one_snapshot(self):
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "first"}, clear=True):
            identity = self.cli.agent_identity()
            identity["host"] = "tampered"
            os.environ["CODEX_THREAD_ID"] = "second"
            os.environ["CORTEX_HOST"] = "claude"
            self.assertEqual(self.cli.agent_session_id(), "first")
            self.assertEqual(self.cli.agent_identity()["host"], "codex")


class DisposableCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cortex-host-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.home = self.root / "state"
        self.log = self.home / "cortex-log.jsonl"

    def run_cli(self, *args, identity=None, project=None, expected=0):
        env = dict(os.environ)
        for key in IDENTITY_KEYS + ("CORTEX_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL",
                                    "CORTEX_OBSIDIAN_ROOT", "CORTEX_REPO"):
            env.pop(key, None)
        env.update(identity or {})
        env["CORTEX_HOME"] = str(self.home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, str(CLI), *args],
                                env=env, cwd=project or self.project,
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def rows(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def route(self, identity, task="host identity", named=False):
        if named:
            self.run_cli("log", "--task", task, "--system", "Claude",
                         "--pattern", "direct", "--tier", "L3", "--model", "claude",
                         "--class", "build", identity=identity)
        else:
            self.run_cli("log-line", "Claude > direct @ L3", task,
                         "--model", "claude", "--class", "build", identity=identity)
        return self.rows()[-1]

    def test_route_and_all_corrections_keep_actor_provenance(self):
        env = {"CODEX_THREAD_ID": "canonical-thread", "CODEX_SESSION_ID": "runtime-id"}
        route = self.route(env)
        original = self.log.read_bytes()
        self.assertEqual(route["host"], "codex")
        self.assertEqual(route["session_ref"], "canonical-thread")
        self.assertEqual(route["session_ref_source"], "CODEX_THREAD_ID")
        self.assertRegex(route["session_id"], r"^\d{4}-\d\d-\d\dT\d\d$")
        self.run_cli("outcome", "partial", identity=env)
        self.run_cli("outcome", "shipped", identity=env)
        self.run_cli("audit-tiers", "--reclassify", route["task_hash"], "--to", "L2", identity=env)
        self.run_cli("reroute", "--to", "Direct > edit @ L2", identity=env)
        rows = self.rows()
        self.assertEqual([r["event"] for r in rows],
                         ["route", "outcome", "outcome", "reclassify", "reroute"])
        self.assertTrue(self.log.read_bytes().startswith(original))
        for row in rows:
            for key in ("host", "host_source", "session_ref", "session_ref_source"):
                self.assertEqual(row[key], route[key])
        for row in rows[1:]:
            self.assertEqual(row["ref"], route["event_id"])

    def test_native_thread_and_project_scoping(self):
        first = {"CODEX_THREAD_ID": "first"}
        second = {"CODEX_THREAD_ID": "second"}
        a = self.route(first)
        self.route(second)
        self.run_cli("outcome", "partial", identity=first)
        self.assertEqual(self.rows()[-1]["ref"], a["event_id"])
        before = self.log.read_bytes()
        self.run_cli("outcome", "shipped", identity={"CODEX_THREAD_ID": "missing"}, expected=1)
        other = self.root / "other" / "project"
        other.mkdir(parents=True)
        self.run_cli("outcome", "shipped", identity=first, project=other, expected=1)
        self.assertEqual(self.log.read_bytes(), before)

    def test_conflict_and_explicit_correction_actor(self):
        route = self.route({"CODEX_THREAD_ID": "thread"})
        mixed = {"CODEX_THREAD_ID": "thread", "CLAUDE_CODE_SESSION_ID": "claude"}
        before = self.log.read_bytes()
        self.run_cli("outcome", "shipped", identity=mixed, expected=1)
        self.assertEqual(self.log.read_bytes(), before)
        ambiguous = self.route(mixed)
        self.assertEqual(ambiguous["host"], "unknown")
        self.assertEqual(ambiguous["host_source"], "conflicting_env")
        self.assertIsNone(ambiguous["session_ref"])
        self.run_cli("outcome", "partial", "--ref", route["event_id"], identity=mixed)
        self.assertIsNone(self.rows()[-1]["session_ref"])
        self.run_cli("outcome", "shipped", "--ref", route["event_id"],
                     identity={**mixed, "CORTEX_HOST": "claude"})
        correction = self.rows()[-1]
        self.assertEqual(correction["host"], "claude")
        self.assertEqual(correction["session_ref"], "claude")
        self.assertEqual(self.rows()[0]["host"], "codex")

    def test_session_override_preserves_implicit_scoping(self):
        env = {"CORTEX_SESSION_ID": " shared ", "CODEX_THREAD_ID": "thread-a"}
        route = self.route(env, named=True)
        self.assertEqual(route["session_ref"], "shared")
        self.assertEqual(route["session_ref_source"], "CORTEX_SESSION_ID")
        self.run_cli("outcome", "shipped", identity={**env, "CODEX_THREAD_ID": "thread-b"})
        self.assertEqual(self.rows()[-1]["ref"], route["event_id"])

    def test_claude_precedence_and_host_override_roundtrip(self):
        env = {"CLAUDE_CODE_SESSION_ID": " primary ", "CLAUDE_SESSION_ID": "secondary",
               "CODEX_THREAD_ID": "thread", "CORTEX_HOST": " CLAUDE "}
        route = self.route(env)
        self.assertEqual(route["session_ref"], "primary")
        self.assertEqual(route["session_ref_source"], "CLAUDE_CODE_SESSION_ID")
        self.run_cli("outcome", "partial", identity=env)
        self.assertEqual(self.rows()[-1]["ref"], route["event_id"])
        codex = self.route({**env, "CORTEX_HOST": "codex"})
        self.assertEqual(codex["session_ref"], "thread")
        self.run_cli("outcome", "shipped", identity={**env, "CORTEX_HOST": "codex"})
        self.assertEqual(self.rows()[-1]["ref"], codex["event_id"])

    def test_hostless_existing_route_keeps_implicit_scope(self):
        env = {"CODEX_THREAD_ID": "existing-scope"}
        route = self.route(env)
        for key in ("host", "host_source", "session_ref_source"):
            route.pop(key)
        self.log.write_text(json.dumps(route) + "\n")
        original = self.log.read_bytes()
        self.run_cli("outcome", "shipped", identity=env)
        self.assertTrue(self.log.read_bytes().startswith(original))
        self.assertEqual(self.rows()[-1]["ref"], route["event_id"])

    def test_known_host_collision_requires_explicit_ref(self):
        claude = {"CLAUDE_CODE_SESSION_ID": "same-id"}
        codex = {"CODEX_THREAD_ID": "same-id"}
        route = self.route(claude)
        before = self.log.read_bytes()
        self.run_cli("outcome", "shipped", identity=codex, expected=1)
        self.run_cli("reroute", "--to", "Direct > edit @ L2", identity=codex, expected=1)
        self.assertEqual(self.log.read_bytes(), before)
        self.run_cli("outcome", "partial", "--ref", route["event_id"], identity=codex)
        self.assertEqual(self.rows()[-1]["ref"], route["event_id"])
        self.assertEqual(self.rows()[-1]["host"], "codex")
        self.run_cli("reroute", "--to", "Direct > edit @ L2",
                     "--ref", route["event_id"], identity=codex)
        self.assertEqual(self.rows()[-1]["ref"], route["event_id"])

    def test_colliding_native_hosts_select_only_their_own_latest_route(self):
        claude = {"CLAUDE_CODE_SESSION_ID": "same-id"}
        codex = {"CODEX_THREAD_ID": "same-id"}
        first = self.route(codex, task="codex task")
        second = self.route(claude, task="claude task")
        self.run_cli("outcome", "partial", identity=codex)
        self.assertEqual(self.rows()[-1]["ref"], first["event_id"])
        third = self.route(codex, task="later codex task")
        self.run_cli("outcome", "partial", identity=claude)
        self.assertEqual(self.rows()[-1]["ref"], second["event_id"])
        self.run_cli("reroute", "--to", "Direct > edit @ L2", identity=codex)
        self.assertEqual(self.rows()[-1]["ref"], third["event_id"])

    def test_session_override_does_not_erase_known_host_boundary(self):
        self.route({"CORTEX_HOST": "claude", "CORTEX_SESSION_ID": "shared"})
        before = self.log.read_bytes()
        self.run_cli("outcome", "shipped", identity={
            "CORTEX_HOST": "codex", "CORTEX_SESSION_ID": "shared"}, expected=1)
        self.assertEqual(self.log.read_bytes(), before)

    def test_session_override_scopes_even_with_host_conflict(self):
        env = {"CORTEX_SESSION_ID": "explicit-scope", "CODEX_THREAD_ID": "thread",
               "CLAUDE_SESSION_ID": "claude"}
        route = self.route(env)
        self.assertEqual(route["host"], "unknown")
        self.assertEqual(route["session_ref"], "explicit-scope")
        self.run_cli("outcome", "shipped", identity=env)
        self.assertEqual(self.rows()[-1]["ref"], route["event_id"])

    def test_codex_runtime_id_is_not_a_transcript_id(self):
        env = {"CODEX_SESSION_ID": "runtime-only"}
        route = self.route(env)
        self.assertEqual(route["host"], "codex")
        self.assertEqual(route["host_source"], "CODEX_SESSION_ID")
        self.assertNotEqual(route["session_ref"], "runtime-only")
        self.assertIn(route["session_ref_source"], (None, "ppid"))

    def test_ppid_fallback_roundtrip_is_not_native_identity(self):
        route = self.route(dict.fromkeys(IDENTITY_KEYS, " \t"))
        self.assertEqual(route["host"], "unknown")
        if route["session_ref"] is None:
            self.assertIsNone(route["session_ref_source"])
            self.run_cli("outcome", "shipped", expected=1)
        else:
            self.assertRegex(route["session_ref"], r"^ppid_[0-9a-f]{10}$")
            self.assertEqual(route["session_ref_source"], "ppid")
            self.run_cli("outcome", "shipped")
            self.assertEqual(self.rows()[-1]["ref"], route["event_id"])

    def test_local_exported_identity_with_disposable_state(self):
        # Exercise the actual calling environment without ever using its state.
        env = {key: os.environ[key] for key in IDENTITY_KEYS if key in os.environ}
        with mock.patch.dict(os.environ, env, clear=True):
            expected = load_cli().agent_identity()
        route = self.route(env)
        for key in ("host", "host_source"):
            self.assertEqual(route[key], expected[key])
        if expected["session_ref_source"] not in (None, "ppid"):
            self.assertEqual(route["session_ref"], expected["session_ref"])
            self.assertEqual(route["session_ref_source"], expected["session_ref_source"])
            self.run_cli("outcome", "shipped", identity=env)


if __name__ == "__main__":
    unittest.main()
