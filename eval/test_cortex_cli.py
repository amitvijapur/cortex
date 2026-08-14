#!/usr/bin/env python3
"""test_cortex_cli — behavioural tests for bin/cortex.

WHY THIS EXISTS
    bin/cortex is invoked unattended: four SessionStart hooks, a launchd Telegram
    bot, and a weekly scout all shell out to it. A break there is silent. These
    tests run every subcommand against a throwaway CORTEX_HOME so the real log is
    never touched, and assert the two properties that are easy to regress:

      1. old-format rows (no `event` key, the 141 already on disk) still parse and
         still produce the same current view;
      2. corrections are appended, never written over — the bytes of an original
         row must be identical before and after an outcome / reroute / reclassify.

    Run:  python3 eval/test_cortex_cli.py [-v]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORTEX = REPO / "bin" / "cortex"

FAILURES = []
VERBOSE = "-v" in sys.argv


def check(name, cond, detail=""):
    if cond:
        if VERBOSE:
            print(f"  ok   {name}")
    else:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")
        print(f"  FAIL {name}{': ' + detail if detail else ''}")


class Sandbox:
    """A disposable CORTEX_HOME. Nothing here can reach the real ~/.claude."""

    def __init__(self, seed_legacy=True):
        self.dir = Path(tempfile.mkdtemp(prefix="cortex-test-"))
        (self.dir / "bin").mkdir()
        (self.dir / "skills").mkdir()
        (self.dir / "agents").mkdir()
        (self.dir / "cortex.md").write_text("# cortex\nregistry\n")
        self.log = self.dir / "cortex-log.jsonl"
        if seed_legacy:
            self.log.write_text("".join(json.dumps(r) + "\n" for r in LEGACY_ROWS))

    def run(self, *args, env=None, timeout=60):
        e = dict(os.environ)
        e["CORTEX_HOME"] = str(self.dir)
        e.pop("CORTEX_OBSIDIAN_ROOT", None)   # don't audit the real vault
        e.pop("CORTEX_REPO", None)
        e.update(env or {})
        return subprocess.run([sys.executable, str(CORTEX), *args],
                              capture_output=True, text=True, env=e, timeout=timeout)

    def lines(self):
        return [l for l in self.log.read_text().splitlines() if l.strip()]

    def rows(self):
        return [json.loads(l) for l in self.lines()]

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


# Rows in the pre-event format actually on disk today: no `event`, no `event_id`,
# and one row already carrying a tier_audit_original from the old in-place path.
LEGACY_ROWS = [
    {"ts": "2026-07-01T10:00:00Z", "session_id": "2026-07-01T10", "project": "cortex",
     "task": "refactor the auth middleware to use the new session store",
     "task_hash": "aaaaaaaaaaaa", "class": "build", "system": "OMC", "pattern": "ralplan",
     "agent": "Backend Architect", "tier": "L3", "tier_reason": "touches auth",
     "system_reason": "needs planning", "confidence": "high", "route_confidence": "high",
     "tier_confidence": "med", "spec_confidence": "high", "legs": None,
     "outcome": "shipped", "redirect_from": None, "user_correction": None},
    {"ts": "2026-07-02T11:00:00Z", "session_id": "2026-07-02T11", "project": "cortex",
     "task": "add a loading state to the submit button", "task_hash": "bbbbbbbbbbbb",
     "class": "build", "system": "OMC", "pattern": "autopilot", "agent": "Frontend Developer",
     "tier": "L2", "tier_reason": "local edit", "system_reason": "well scoped",
     "outcome": None, "redirect_from": None, "user_correction": None},
    {"ts": "2026-07-03T12:00:00Z", "session_id": "2026-07-03T12", "project": "other",
     "task": "write the release notes for v2", "task_hash": "cccccccccccc",
     "class": "build", "system": "OMC", "pattern": "autopilot", "agent": "Content Creator",
     "tier": "L2", "tier_reason": "reclassified by hand", "system_reason": "doc work",
     "outcome": "shipped", "redirect_from": None, "user_correction": None,
     "tier_audit_original": "L3", "tier_audit_note": "L2 would have done"},
]


def test_legacy_rows_still_read(sb):
    print("\n[1] old-format rows still parse")
    r = sb.run("show", "--last", "10")
    check("show exits 0", r.returncode == 0, r.stderr[-300:])
    check("show renders all 3 legacy routes", r.stdout.count("route:") == 3, r.stdout)
    check("show reports the total", "3 total" in r.stdout, r.stdout)

    r = sb.run("audit-tiers")
    check("audit-tiers sees the L3 route", "aaaaaaaaaaaa" in r.stdout, r.stdout)
    # The legacy row that was reclassified in place is L2 now, so it correctly
    # falls outside the default L3/L4 view — but its provenance must survive.
    r = sb.run("audit-tiers", "--tier", "L2")
    check("legacy in-place reclassification is preserved",
          "reclassified from L3" in r.stdout, r.stdout)

    r = sb.run("hint", "refactor the auth middleware session store", "--class", "build")
    check("hint exits 0", r.returncode == 0, r.stderr[-300:])
    check("hint finds the similar legacy route", "ralplan" in r.stdout, r.stdout)

    # The regression this guards: hint used to gate on Jaccard >= 0.15 by default, which
    # silenced it on 89% of real queries to buy 1.3% top-5 route recall (eval/hint_arms.py).
    # A lexically unrelated query must still return the recent routes in its class, because
    # recency scored 20.8% on the same replay. If this ever goes quiet again, the gate is
    # back.
    r = sb.run("hint", "provision the kubernetes ingress controller", "--class", "build")
    check("hint stays useful on a lexically unrelated query",
          "no similar past tasks" not in r.stdout and "ralplan" in r.stdout, r.stdout)
    check("hint shows similarity without ranking on it", "sim 0.00" in r.stdout, r.stdout)

    # Narrowing must still be available, just not as the default.
    r = sb.run("hint", "provision the kubernetes ingress controller", "--class", "build",
               "--min-similarity", "0.9")
    check("--min-similarity still narrows when asked",
          "no past routes above similarity" in r.stdout, r.stdout)

    r = sb.run("learn", "--threshold", "2", "--no-proposals")
    check("learn groups legacy rows", "autopilot" in r.stdout, r.stdout)

    r = sb.run("learn", "--check")
    check("learn --check exits 0", r.returncode == 0, r.stderr[-300:])


def test_append_only_roundtrip(sb):
    print("\n[2] corrections append, originals are byte-identical")
    before = sb.lines()

    r = sb.run("log-line", "OMC > ralplan > Backend Architect @ L3",
               "make the cortex log append-only", "--class", "build",
               "--tier-reason", "baseline integrity", "--confidence", "high")
    check("log-line exits 0", r.returncode == 0, r.stderr[-300:])
    after_log = sb.lines()
    check("log-line appended exactly one line", len(after_log) == len(before) + 1)
    check("log-line left prior lines untouched", after_log[:len(before)] == before)

    new_row = json.loads(after_log[-1])
    check("new row is marked as a route event", new_row.get("event") == "route")
    for field in ("event_id", "run_id", "cortex_md_sha"):
        check(f"new row carries {field}", bool(new_row.get(field)), repr(new_row.get(field)))
    check("legacy session_id field kept", "session_id" in new_row)

    # outcome
    snapshot = sb.lines()
    r = sb.run("outcome", "shipped", "--note", "landed clean")
    check("outcome exits 0", r.returncode == 0, r.stderr[-300:])
    check("outcome appended one line", len(sb.lines()) == len(snapshot) + 1)
    check("outcome did not rewrite any prior line", sb.lines()[:len(snapshot)] == snapshot)
    ev = json.loads(sb.lines()[-1])
    check("outcome event references the route",
          ev.get("event") == "outcome" and ev.get("ref") == new_row["event_id"], json.dumps(ev))
    check("outcome event carries outcome for naive tail readers",
          ev.get("outcome") == "shipped")

    r = sb.run("show", "--last", "1")
    check("derived view shows SHIPPED", "[SHIPPED]" in r.stdout, r.stdout)

    # reclassify
    snapshot = sb.lines()
    task_hash = new_row["task_hash"]
    r = sb.run("audit-tiers", "--reclassify", task_hash, "--to", "L2", "--note", "L2 was enough")
    check("reclassify exits 0", r.returncode == 0, r.stderr[-300:])
    check("reclassify appended one line", len(sb.lines()) == len(snapshot) + 1)
    check("reclassify did not rewrite the route row", sb.lines()[:len(snapshot)] == snapshot)
    check("the original row still says L3",
          json.loads(sb.lines()[len(before)])["tier"] == "L3")

    r = sb.run("audit-tiers", "--tier", "L2")
    check("derived tier is now L2", task_hash in r.stdout, r.stdout)
    check("derived view remembers the original tier",
          "reclassified from L3" in r.stdout, r.stdout)
    r = sb.run("audit-tiers")
    check("route no longer appears under L3", task_hash not in r.stdout, r.stdout)

    r = sb.run("audit-tiers", "--reclassify", task_hash, "--to", "L2")
    check("re-reclassifying to the same tier is a no-op",
          "nothing to do" in r.stdout, r.stdout)

    # reroute
    snapshot = sb.lines()
    r = sb.run("reroute", "--to", "GSD > /gsd-do @ L2")
    check("reroute exits 0", r.returncode == 0, r.stderr[-300:])
    check("reroute appended one line", len(sb.lines()) == len(snapshot) + 1)
    check("reroute did not rewrite prior lines", sb.lines()[:len(snapshot)] == snapshot)

    r = sb.run("show", "--last", "1")
    check("derived view shows CORRECTED", "[CORRECTED]" in r.stdout, r.stdout)

    # history: the chain must be recoverable
    r = sb.run("history", task_hash)
    check("history exits 0", r.returncode == 0, r.stderr[-300:])
    for expected in ("outcome", "reclassify", "reroute", "tier as first logged: L3"):
        check(f"history shows {expected!r}", expected in r.stdout, r.stdout)

    # a second reclassification must not lose the true original
    sb.run("audit-tiers", "--reclassify", task_hash, "--to", "L4", "--note", "changed mind")
    r = sb.run("history", task_hash)
    check("original tier survives a second reclassification",
          "tier as first logged: L3" in r.stdout, r.stdout)

    # learn must ignore corrected routes, as it did before
    r = sb.run("learn", "--threshold", "1", "--no-proposals")
    check("learn skips the corrected route",
          "make the cortex log append-only" not in r.stdout, r.stdout)


def test_outcome_targeting(sb):
    print("\n[3] outcome targets the open route in this project")
    # The legacy row 'bbbb' has no outcome and belongs to project 'cortex'.
    cwd = REPO  # project_name() == 'cortex'
    e = dict(os.environ)
    e["CORTEX_HOME"] = str(sb.dir)
    r = subprocess.run([sys.executable, str(CORTEX), "outcome", "partial"],
                       capture_output=True, text=True, env=e, cwd=cwd, timeout=60)
    check("outcome exits 0", r.returncode == 0, r.stderr[-300:])
    ev = json.loads(sb.lines()[-1])
    check("targeted the still-open legacy row", ev.get("ref", "").startswith("lg_"), json.dumps(ev))
    r = sb.run("show", "--last", "10")
    check("legacy row now shows PARTIAL", "[PARTIAL]" in r.stdout, r.stdout)


def test_orphan_events(sb):
    print("\n[4] orphaned correction events are reported, not crashed on")
    with sb.log.open("a") as f:
        f.write(json.dumps({"ts": "2026-07-09T09:00:00Z", "event": "outcome",
                            "event_id": "ev_orphan", "ref": "ev_does_not_exist",
                            "outcome": "shipped"}) + "\n")
    r = sb.run("show", "--last", "5")
    check("show survives an orphan event", r.returncode == 0, r.stderr[-300:])
    check("orphan is not rendered as a route", "None > None" not in r.stdout, r.stdout)
    r = sb.run("doctor", "--no-probe", "-v")
    check("doctor reports the orphan",
          "reference a route that is not in the log" in r.stdout, r.stdout)


def test_other_subcommands(sb):
    print("\n[5] every other subcommand still works")
    r = sb.run("intake", "add", "https://example.com/thing", "--note", "check this")
    check("intake add exits 0", r.returncode == 0, r.stderr[-300:])
    check("intake count sees it", sb.run("intake", "count").stdout.strip() == "1")
    check("intake list exits 0", sb.run("intake", "list").returncode == 0)

    r = sb.run("installs", "add", "--label", "thing", "--command", "echo hi")
    check("installs add exits 0", r.returncode == 0, r.stderr[-300:])
    check("installs count sees it", sb.run("installs", "count").stdout.strip() == "1")
    check("installs --labels works", "thing" in sb.run("installs", "list", "--labels").stdout)

    r = sb.run("init", "--dry-run")
    check("init --dry-run exits 0", r.returncode == 0, r.stderr[-300:])

    r = sb.run("doctor", "--no-probe")
    check("doctor runs (fails on missing skills, as designed)", r.returncode in (0, 1), r.stderr[-300:])
    check("doctor reports the missing skills", "skill missing" in r.stdout, r.stdout)

    r = sb.run("show", "--project", "nope")
    check("show --project on an unknown project is graceful", r.returncode == 0, r.stderr[-300:])


def test_empty_log():
    print("\n[6] an empty log is handled everywhere")
    sb = Sandbox(seed_legacy=False)
    try:
        for args in (["show"], ["learn"], ["learn", "--check"], ["hint", "anything at all"],
                     ["audit-tiers"], ["outcome", "shipped"], ["reroute", "--to", "X @ L2"],
                     ["history", "deadbeef"], ["doctor", "--no-probe"]):
            r = sb.run(*args)
            check(f"{' '.join(args)} on empty log", r.returncode in (0, 1), r.stderr[-300:])
            check(f"{' '.join(args)} wrote nothing", not sb.log.exists() or not sb.lines())
    finally:
        sb.close()


def test_doctor_artifact_integrity():
    print("\n[7] doctor detects a diverged copy of the CLI")
    sb = Sandbox()
    try:
        # healthy: the CLI on PATH is a symlink into the repo checkout
        link = sb.dir / "bin" / "cortex"
        link.symlink_to(CORTEX)
        r = sb.run("doctor", "--no-probe", "-v")
        check("symlinked install passes the content check",
              "cortex CLI matches repo source" in r.stdout, r.stdout)
        check("symlinked install is not flagged as a copy",
              "standalone copy" not in r.stdout, r.stdout)

        # broken: a standalone copy that has drifted from the repo source
        link.unlink()
        copy = sb.dir / "bin" / "cortex"
        copy.write_text(CORTEX.read_text() + "\n# drifted a month ago\n")
        copy.chmod(0o755)
        r = sb.run("doctor", "--no-probe")
        check("diverged copy is a FAIL",
              "differs from repo source" in r.stdout and r.returncode == 1, r.stdout)
        check("diverged copy is also flagged as unlinked",
              "standalone copy" in r.stdout, r.stdout)

        # and the same when the diverged copy is the one being executed —
        # the real drift incident, where the stale CLI audits itself.
        r = subprocess.run([sys.executable, str(copy), "doctor", "--no-probe"],
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, "CORTEX_HOME": str(sb.dir),
                                "CORTEX_REPO": str(REPO)})
        check("a stale CLI auditing itself reports the drift",
              "differs from repo source" in r.stdout, r.stdout)

        # unreachable source: honest "cannot verify", not a false pass
        r = subprocess.run([sys.executable, str(copy), "doctor", "--no-probe"],
                           capture_output=True, text=True, timeout=60,
                           env={**{k: v for k, v in os.environ.items() if k != "CORTEX_REPO"},
                                "CORTEX_HOME": str(sb.dir)})
        check("no reachable source reports unknown rather than pass",
              "repo source not reachable" in r.stdout, r.stdout)
    finally:
        sb.close()


def fake_cli(path, name, body):
    p = path / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(0o755)
    return p


def test_doctor_advisor_probes():
    print("\n[8] doctor probes the advisor CLIs")
    sb = Sandbox()
    fakebin = sb.dir / "fakebin"
    fakebin.mkdir()
    path = f"{fakebin}:{os.environ.get('PATH', '')}"
    try:
        # all healthy
        fake_cli(fakebin, "codex", 'echo "codex-cli 9.9.9"')
        fake_cli(fakebin, "gemini", 'echo "9.9.9"')
        r = sb.run("doctor", "-v", env={"PATH": path, "CORTEX_ADVISORS": "codex,gemini"})
        check("healthy advisors pass", "advisor codex responds" in r.stdout, r.stdout)
        check("liveness-only caveat is stated",
              "liveness only" in r.stdout, r.stdout)

        # installed but broken — the failure mode --version alone would miss if we
        # only checked for the binary's existence
        fake_cli(fakebin, "codex", 'echo "auth expired" >&2; exit 1')
        r = sb.run("doctor", env={"PATH": path, "CORTEX_ADVISORS": "codex,gemini"})
        check("broken advisor is reported",
              "advisor codex is installed but not working" in r.stdout, r.stdout)
        check("the reason is surfaced", "auth expired" in r.stdout, r.stdout)

        # both dead -> FAIL, because /ccg then has no provider at all
        fake_cli(fakebin, "gemini", "exit 3")
        r = sb.run("doctor", env={"PATH": path, "CORTEX_ADVISORS": "codex,gemini"})
        check("all providers dead is a FAIL",
              "no advisor CLI responded" in r.stdout and r.returncode == 1, r.stdout)

        # a hanging CLI must report unknown and must not hang doctor
        fake_cli(fakebin, "codex", "sleep 60")
        fake_cli(fakebin, "gemini", 'echo "9.9.9"')
        r = sb.run("doctor", timeout=40,
                   env={"PATH": path, "CORTEX_ADVISORS": "codex,gemini",
                        "CORTEX_HOME": str(sb.dir)})
        check("a hanging advisor reports unknown, not dead",
              "advisor codex status unknown" in r.stdout, r.stdout)

        # all probes inconclusive must NOT fail doctor — a timeout is not proof of death
        fake_cli(fakebin, "gemini", "sleep 60")
        r = sb.run("doctor", timeout=40,
                   env={"PATH": path, "CORTEX_ADVISORS": "codex,gemini"})
        check("all-timeout stays a warn, not a fail",
              "could not confirm any advisor CLI is working" in r.stdout
              and "no advisor CLI responded" not in r.stdout,
              r.stdout)

        # missing required vs missing optional
        r = sb.run("doctor", "-v", env={"PATH": str(fakebin) + ":/usr/bin:/bin",
                                        "CORTEX_ADVISORS": "gemini,agy?"})
        check("optional advisor absence is not a warning",
              "not installed (optional)" in r.stdout, r.stdout)
    finally:
        sb.close()


def main():
    sb = Sandbox()
    try:
        test_legacy_rows_still_read(sb)
        test_append_only_roundtrip(sb)
        test_outcome_targeting(sb)
        test_orphan_events(sb)
        test_other_subcommands(sb)
    finally:
        sb.close()
    test_empty_log()
    test_doctor_artifact_integrity()
    test_doctor_advisor_probes()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
