#!/usr/bin/env python3
"""Isolated runtime regression tests. No installed state, models, or agents.

Run with PYTHONDONTWRITEBYTECODE=1 python3 eval/test_cortex_integrity.py.
Queue workers deliberately delay after reading to expose lost-update races.
Holding the stable lock before releasing workers also proves the read is inside
the transaction, independently of scheduler luck or final-write locking.

Set CORTEX_INTAKE_COMMON to a staged common.py to additionally test mixed CLI /
intake writers. The module is copied into a disposable directory before import.
"""
import contextlib
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


CLI = Path(__file__).resolve().parents[1] / "bin" / "cortex"


def load_cli(path=CLI):
    loader = importlib.machinery.SourceFileLoader("cortex_integrity", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def queue_worker():
    marker, gate, *argv = sys.argv[2:]
    is_common = argv[1].startswith("--common-")
    module = load_cli(os.environ["CORTEX_INTAKE_COMMON_COPY"] if is_common else CLI)
    if is_common:
        module.INBOX_PATH = Path(os.environ["CORTEX_HOME"]) / "cortex-inbox.jsonl"
        module.INSTALL_QUEUE_PATH = Path(os.environ["CORTEX_HOME"]) / "cortex-install-queue.jsonl"
        original_read = Path.read_text

        def delayed_path_read(path, *args, **kwargs):
            rows = original_read(path, *args, **kwargs)
            if path in (module.INBOX_PATH, module.INSTALL_QUEUE_PATH):
                Path(marker + ".read").touch()
                time.sleep(0.04)
            return rows

        Path.read_text = delayed_path_read
    else:
        reader_name = "read_inbox" if argv[0] == "intake" else "read_installs"
        original = getattr(module, reader_name)

        def delayed_read():
            Path(marker + ".read").touch()
            rows = original()
            time.sleep(0.04)
            return rows

        setattr(module, reader_name, delayed_read)
    Path(marker).touch()
    deadline = time.monotonic() + 15
    while not Path(gate).exists():
        if time.monotonic() > deadline:
            raise RuntimeError("worker start gate timed out")
        time.sleep(0.005)
    if is_common:
        action, value = argv[1:]
        if action == "--common-add":
            module.append_entry(dict(id=value, url=value, status="pending"))
        elif action == "--common-update":
            if module.update_entry(value, verdict="common verdict") is None:
                raise AssertionError("common failed to find update target")
        elif action == "--common-install":
            module.add_install(value, ["echo test"], source_id=value)
        else:
            raise AssertionError(action)
        return 0
    args = module.build_parser().parse_args(argv)
    return args.func(args)


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cortex-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "state"
        self.home.mkdir()
        self.project = self.root / "project-a"
        self.project.mkdir()
        self.other = self.root / "project-b"
        self.other.mkdir()
        self.env = dict(os.environ, CORTEX_HOME=str(self.home),
                        CLAUDE_DIR=str(self.home), HOME=str(self.root),
                        CORTEX_SESSION_ID="session-a", PYTHONDONTWRITEBYTECODE="1")
        for name in ("CORTEX_OBSIDIAN_ROOT", "CORTEX_REPO"):
            self.env.pop(name, None)
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.cli = load_cli()
        self.log = self.home / "cortex-log.jsonl"

    def run_cli(self, *args, session="session-a", cwd=None, ok=True):
        env = dict(self.env, CORTEX_SESSION_ID=session)
        result = subprocess.run([sys.executable, str(CLI), *args], env=env,
                                cwd=cwd or self.project, capture_output=True,
                                text=True, timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def rows(self, path=None):
        path = path or self.log
        return [json.loads(line) for line in path.read_text().splitlines()]

    def seed(self, rows):
        self.log.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def route(self, task="current", **kwargs):
        self.run_cli("log-line", "Direct > fix @ L2", task, "--class", "debug", **kwargs)
        return self.rows()[-1]["event_id"]

    def legacy(self, **changes):
        row = dict(ts="2026-01-01T00:00:00Z", task="same task", task_hash="same-hash",
                   project="project-a", system="Direct", pattern="fix", tier="L2",
                   outcome=None)
        row.update(changes)
        return row

    def old_ref(self, row):
        # Independent historical formula, so changing the implementation cannot
        # accidentally make both the fixture and the assertion agree.
        seed = "|".join(str(row.get(k)) for k in ("ts", "task_hash", "system", "pattern"))
        return "lg_" + hashlib.sha1(seed.encode()).hexdigest()[:12]

    def test_latest_task_survives_partial_to_shipped(self):
        older = self.route("older unfinished")
        current = self.route("new task")
        self.route("another session", session="session-b")
        self.route("another project", cwd=self.other)
        before = self.log.read_bytes()
        self.run_cli("outcome", "partial")
        self.run_cli("outcome", "shipped")
        self.assertTrue(self.log.read_bytes().startswith(before))
        self.assertEqual([r["ref"] for r in self.rows()[-2:]], [current, current])
        view = {r["_id"]: r for r in self.cli.read_log()}
        self.assertIsNone(view[older]["outcome"])
        self.assertEqual(view[current]["outcome"], "shipped")

    def test_reroute_respects_project_and_session(self):
        current = self.route()
        self.route(session="session-b")
        self.route(cwd=self.other)
        self.run_cli("reroute", "--to", "Direct > other @ L2")
        self.assertEqual(self.rows()[-1]["ref"], current)

    def test_same_basename_projects_do_not_share_implicit_targets(self):
        first, second = self.root / "one" / "api", self.root / "two" / "api"
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        target = self.route("first api", cwd=first)
        other = self.route("second api", cwd=second)
        routes = self.rows()
        self.assertEqual([r["project"] for r in routes], ["api", "api"])
        self.assertEqual([r["project_ref"] for r in routes],
                         [str(first.resolve()), str(second.resolve())])
        self.run_cli("outcome", "partial", cwd=first)
        self.run_cli("outcome", "shipped", cwd=first)
        self.run_cli("reroute", "--to", "X", cwd=first)
        self.assertEqual([r["ref"] for r in self.rows()[-3:]], [target] * 3)
        view = {r["_id"]: r for r in self.cli.read_log()}
        self.assertIsNone(view[other]["outcome"])

    def test_project_labels_do_not_override_canonical_scope(self):
        self.run_cli("log-line", "Direct > fix @ L2", "task", "--class", "debug",
                     "--project", "custom display label")
        target = self.rows()[0]["event_id"]
        self.run_cli("outcome", "shipped")
        self.assertEqual(self.rows()[-1]["ref"], target)

    def test_missing_canonical_project_path_requires_explicit_ref(self):
        target = self.route()
        rows = self.rows()
        del rows[0]["project_ref"]
        self.seed(rows)
        before = self.log.read_bytes()
        for argv in (("outcome", "shipped"), ("reroute", "--to", "X")):
            self.run_cli(*argv, ok=False)
            self.assertEqual(self.log.read_bytes(), before)
        self.run_cli("outcome", "shipped", "--ref", target)
        self.assertEqual(self.rows()[-1]["ref"], target)

    def test_no_implicit_fallback(self):
        for scenario in ("empty", "other-project", "other-session", "legacy"):
            with self.subTest(scenario=scenario):
                self.seed([])
                if scenario == "other-project":
                    self.route(cwd=self.other)
                elif scenario == "other-session":
                    self.route(session="session-b")
                elif scenario == "legacy":
                    self.seed([self.legacy()])
                before = self.log.read_bytes()
                for argv in (("outcome", "shipped"), ("reroute", "--to", "X")):
                    result = self.run_cli(*argv, ok=False)
                    self.assertIn("--ref", result.stderr)
                    self.assertEqual(self.log.read_bytes(), before)

    def test_explicit_ref_overrides_scope(self):
        target = self.route(cwd=self.other, session="session-b")
        self.route()
        self.run_cli("outcome", "shipped", "--ref", target)
        self.run_cli("reroute", "--to", "X", "--ref", target)
        self.assertEqual([r["ref"] for r in self.rows()[-2:]], [target, target])

    def test_invalid_ref_and_task_hash_never_fall_back(self):
        self.route()
        for ref in ("", "ev_missing", self.rows()[0]["task_hash"]):
            before = self.log.read_bytes()
            for argv in (("outcome", "shipped"), ("reroute", "--to", "X")):
                self.run_cli(*argv, "--ref", ref, ok=False)
                self.assertEqual(self.log.read_bytes(), before)

    def test_missing_session_requires_explicit_ref(self):
        target = self.route()
        entries = self.cli.read_log()
        with mock.patch.object(self.cli, "agent_session_id", return_value=None):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertIsNone(self.cli.correction_target(entries))
            self.assertEqual(self.cli.correction_target(entries, target)["_id"], target)

    def test_collapsed_rows_are_json_serializable(self):
        row = self.legacy()
        self.seed([row, dict(event="outcome", ref=self.old_ref(row), outcome="partial")])
        view = self.cli.read_log()
        self.assertEqual(json.loads(json.dumps(view)), view)
        self.assertEqual(view[0]["_refs"], sorted(view[0]["_refs"]))

    def test_corrected_current_task_does_not_reopen_older(self):
        self.route("older")
        self.route("current")
        self.run_cli("reroute", "--to", "X")
        before = self.log.read_bytes()
        self.run_cli("outcome", "shipped")
        self.assertEqual(self.log.read_bytes(), before)

    def test_unique_old_correction_refs_keep_full_chain(self):
        row = self.legacy()
        ref = self.old_ref(row)
        corrections = [dict(event="outcome", ref=ref, outcome="partial"),
                       dict(event="reclassify", ref=ref, tier="L3"),
                       dict(event="reroute", ref=ref, user_correction="X")]
        self.seed([row, *corrections])
        before = self.log.read_bytes()
        view = self.cli.read_log()[0]
        self.assertEqual(view["outcome"], "corrected")
        self.assertEqual(view["tier"], "L3")
        self.assertEqual(view["tier_audit_original"], "L2")
        self.assertEqual(view["_corrections"], corrections)
        self.assertEqual(self.cli.orphan_events(self.rows()), [])
        history = self.run_cli("history", ref)
        self.assertIn(view["_id"], history.stdout)
        self.assertEqual(self.log.read_bytes(), before)

    def test_legacy_alias_targets_unique_row_with_new_ref(self):
        row = self.legacy()
        self.seed([row])
        self.run_cli("outcome", "partial", "--ref", self.old_ref(row))
        self.assertEqual(self.rows()[-1]["ref"], self.cli.entry_id(row))
        self.assertEqual(self.cli.read_log()[0]["outcome"], "partial")

    def test_legacy_collisions_are_detected_and_disambiguated(self):
        a, b = self.legacy(), self.legacy(project="project-b")
        ref = self.old_ref(a)
        self.assertEqual(ref, self.old_ref(b))
        self.assertNotEqual(self.cli.entry_id(a), self.cli.entry_id(b))
        correction = dict(event="outcome", ref=ref, outcome="shipped")
        self.seed([a, b, correction])
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            view = self.cli.read_log()
        self.assertIn("ambiguous", stderr.getvalue())
        self.assertEqual([e["outcome"] for e in view], [None, None])
        self.assertEqual(self.cli.orphan_events(self.rows()), [correction])
        before = self.log.read_bytes()
        for argv in (("outcome", "shipped"), ("reroute", "--to", "X")):
            result = self.run_cli(*argv, "--ref", ref, ok=False)
            self.assertIn("ambiguous", result.stderr)
            self.assertEqual(self.log.read_bytes(), before)
        history = self.run_cli("history", ref)
        self.assertIn(self.cli.entry_id(a), history.stdout)
        self.assertIn(self.cli.entry_id(b), history.stdout)
        self.run_cli("outcome", "partial", "--ref", self.cli.entry_id(a))
        with contextlib.redirect_stderr(io.StringIO()):
            view = self.cli.read_log()
        self.assertEqual([e["outcome"] for e in view], ["partial", None])

    def test_identical_rows_and_duplicate_event_ids_are_not_targetable(self):
        for row in (self.legacy(), self.legacy(event_id="ev_duplicate",
                                              session_ref="session-a")):
            with self.subTest(event_id=row.get("event_id")):
                self.seed([row, row])
                before = self.log.read_bytes()
                for argv in (("outcome", "shipped"), ("reroute", "--to", "X")):
                    result = self.run_cli(*argv, "--ref", self.cli.entry_id(row), ok=False)
                    self.assertIn("ambiguous", result.stderr)
                    self.assertEqual(self.log.read_bytes(), before)
                if row.get("session_ref"):
                    self.run_cli("outcome", "shipped", ok=False)
                    self.assertEqual(self.log.read_bytes(), before)

    def concurrent_queue(self, queue, commands):
        filename = "cortex-inbox.jsonl" if queue == "intake" else "cortex-install-queue.jsonl"
        path = self.home / filename
        lock = path.with_name(path.name + ".lock")
        work = Path(tempfile.mkdtemp(dir=self.root))
        gate = work / "go"
        workers = []
        try:
            with lock.open("a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                for i, command in enumerate(commands):
                    marker = work / str(i)
                    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                             "--worker", str(marker), str(gate), queue, *command],
                                            env=self.env, cwd=self.project,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    workers.append((proc, marker))
                deadline = time.monotonic() + 15
                while not all(marker.exists() for _, marker in workers):
                    self.assertLess(time.monotonic(), deadline, "worker startup timed out")
                    time.sleep(0.01)
                gate.touch()
                time.sleep(0.2)
                self.assertFalse(any(Path(str(marker) + ".read").exists() for _, marker in workers),
                                 "a writer read the queue before acquiring the transaction lock")
                self.assertTrue(all(proc.poll() is None for proc, _ in workers))
                fcntl.flock(held, fcntl.LOCK_UN)
            for proc, _ in workers:
                stdout, stderr = proc.communicate(timeout=20)
                self.assertEqual(proc.returncode, 0, stdout + stderr)
        finally:
            for proc, _ in workers:
                if proc.poll() is None:
                    proc.kill()
                proc.communicate()
        return self.rows(path)

    def test_concurrent_intake_adds_and_resolves(self):
        self.run_cli("intake", "add", "https://example.test/initial")
        path = self.home / "cortex-inbox.jsonl"
        initial = self.rows(path)[0]["id"]
        commands = [("add", f"https://example.test/{i}") for i in range(12)]
        commands.append(("resolve", initial, "--status", "integrated", "--note", "verified"))
        rows = self.concurrent_queue("intake", commands)
        self.assertEqual(len(rows), 13)
        self.assertEqual(len({r["id"] for r in rows}), 13)
        self.assertEqual({r["url"] for r in rows},
                         {"https://example.test/initial", *[f"https://example.test/{i}" for i in range(12)]})
        target = next(r for r in rows if r["id"] == initial)
        self.assertEqual(target["status"], "integrated")
        self.assertEqual(target["verdict"], "verified")

    def test_concurrent_install_add_done_skip_clear(self):
        for label in ("finish", "skip", "clear"):
            self.run_cli("installs", "add", "--label", label, "--command", "echo test")
        path = self.home / "cortex-install-queue.jsonl"
        ids = {r["label"]: r["id"] for r in self.rows(path)}
        commands = [("add", "--label", f"new-{i}", "--command", "echo test") for i in range(12)]
        commands.extend([("done", ids["finish"]), ("skip", ids["skip"]), ("clear",)])
        rows = self.concurrent_queue("installs", commands)
        self.assertEqual(len(rows), 15)
        self.assertEqual(len({r["id"] for r in rows}), 15)
        states = {r["label"]: r["status"] for r in rows}
        self.assertEqual(states["finish"], "done")
        self.assertEqual(states["skip"], "skipped")
        self.assertEqual(states["clear"], "done")

    def stage_common(self):
        source = os.environ.get("CORTEX_INTAKE_COMMON")
        if not source:
            self.skipTest("set CORTEX_INTAKE_COMMON to validate a staged intake module")
        copy = self.root / "intake" / "common.py"
        copy.parent.mkdir()
        shutil.copy2(source, copy)
        self.env["CORTEX_INTAKE_COMMON_COPY"] = str(copy)

    def test_mixed_cli_and_common_inbox_transactions(self):
        self.stage_common()
        self.run_cli("intake", "add", "initial")
        path = self.home / "cortex-inbox.jsonl"
        initial = self.rows(path)[0]["id"]
        commands = [("add", f"cli-{i}") for i in range(6)]
        commands += [("--common-add", f"common-{i}") for i in range(6)]
        commands += [("resolve", initial, "--status", "integrated"),
                     ("--common-update", initial)]
        rows = self.concurrent_queue("intake", commands)
        self.assertEqual(len(rows), 13)
        self.assertEqual({r["url"] for r in rows},
                         {"initial", *[f"cli-{i}" for i in range(6)],
                          *[f"common-{i}" for i in range(6)]})
        entry = next(r for r in rows if r["id"] == initial)
        self.assertEqual(entry["status"], "integrated")
        self.assertEqual(entry["verdict"], "common verdict")

    def test_mixed_cli_and_common_install_transactions(self):
        self.stage_common()
        self.run_cli("installs", "add", "--label", "initial", "--command", "echo test")
        path = self.home / "cortex-install-queue.jsonl"
        initial = self.rows(path)[0]["id"]
        commands = [("add", "--label", f"cli-{i}", "--command", "echo test") for i in range(6)]
        commands += [("--common-install", f"common-{i}") for i in range(6)]
        commands += [("--common-install", "same-source") for _ in range(4)]
        commands += [("done", initial)]
        rows = self.concurrent_queue("installs", commands)
        self.assertEqual(len(rows), 14)
        self.assertEqual(len({r["id"] for r in rows}), 14)
        self.assertEqual(sum(r.get("source_id") == "same-source" for r in rows), 1)
        self.assertEqual(next(r for r in rows if r["id"] == initial)["status"], "done")

    def test_atomic_replacement_failure_preserves_snapshot_and_cleans_temp(self):
        for path in (self.cli.INBOX_PATH, self.cli.INSTALL_QUEUE_PATH):
            path.write_text('{"id":"original"}\n')
            before = path.read_bytes()
            with mock.patch.object(self.cli.os, "replace", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    with self.cli.queue_transaction(path):
                        self.cli.atomic_queue_write(path, [{"id": "replacement"}])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(self.home.glob(path.name + ".*.tmp")), [])

    def test_readers_see_complete_snapshots_during_replacement(self):
        for path in (self.cli.INBOX_PATH, self.cli.INSTALL_QUEUE_PATH):
            with self.subTest(queue=path.name):
                old = [{"id": i, "generation": 0, "payload": "x" * 4096} for i in range(64)]
                with self.cli.queue_transaction(path):
                    self.cli.atomic_queue_write(path, old)
                path.chmod(0o640)
                stop, observed, errors = threading.Event(), threading.Event(), []

                def reader():
                    try:
                        while not stop.is_set():
                            rows = self.rows(path)
                            self.assertEqual([r["id"] for r in rows], list(range(64)))
                            self.assertEqual(len({r["generation"] for r in rows}), 1)
                            observed.set()
                    except BaseException as exc:
                        errors.append(exc)

                thread = threading.Thread(target=reader)
                thread.start()
                try:
                    self.assertTrue(observed.wait(3))
                    for generation in range(1, 16):
                        rows = [dict(row, generation=generation) for row in old]
                        with self.cli.queue_transaction(path):
                            self.cli.atomic_queue_write(path, rows)
                finally:
                    stop.set()
                    thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(path.stat().st_mode & 0o777, 0o640)
                self.assertEqual(self.rows(path)[0]["generation"], 15)

    def test_first_write_creates_state_directory(self):
        nested = self.home / "new" / "state"
        with mock.patch.dict(os.environ, {"CORTEX_HOME": str(nested)}):
            module = load_cli()
        for argv in (("intake", "add", "https://example.test"),
                     ("installs", "add", "--label", "first", "--command", "echo test")):
            args = module.build_parser().parse_args(argv)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(args.func(args), 0)
        self.assertEqual(len(self.rows(nested / "cortex-inbox.jsonl")), 1)
        self.assertEqual(len(self.rows(nested / "cortex-install-queue.jsonl")), 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.exit(queue_worker() or 0)
    unittest.main(verbosity=2)
