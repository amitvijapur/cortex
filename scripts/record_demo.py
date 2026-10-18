#!/usr/bin/env python3
"""Capture a disposable, offline CLI walkthrough; optionally export a GIF.

Default: replay and write examples/demo-session.json. --gif also renders the
capture using optional Pillow. --check replays and verifies without writing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "cortex"
CAPTURE = ROOT / "examples" / "demo-session.json"
GIF = ROOT / "assets" / "cortex-demo.gif"
TASK = "Record a local Cortex CLI walkthrough"
ROUTE = "Direct > cli-walkthrough @ L2"
REASON = "Bounded local demonstration with focused checks"
NOTE = "CLI walkthrough completed; no software changed"
DISCLOSURE = "CLI walkthrough · scripted inputs · real output · no model invoked"
READ_ID = ('import json, os; from pathlib import Path; '
           'rows = (Path(os.environ["CORTEX_HOME"]) / "cortex-log.jsonl").read_text().splitlines(); '
           'print(json.loads(rows[-1])["event_id"])')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def replay():
    """No inherited agent/provider environment or writes to personal state."""
    base = "/private/tmp" if sys.platform == "darwin" else None
    with tempfile.TemporaryDirectory(prefix="cortex-demo-", dir=base) as tmp:
        state = Path(tmp) / "state"
        project = Path(tmp) / "demo-project"
        project.mkdir()
        # These are the only environment variables passed to child processes.
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "CORTEX_HOME": str(state)}
        steps = []
        substitutions = {str(project.resolve()): "<demo-project>"}

        def normalized(value):
            for actual, label in substitutions.items():
                value = value.replace(actual, label)
            value = re.sub(r"\b\d{4}-\d{2}-\d{2} \d{2}:\d{2}\b", "<time>", value)
            value = re.sub(r"run_[a-f0-9]{12}\b", "<run-id>", value)
            value = re.sub(r"ppid:\d+\b", "<process-session>", value)
            return value

        def execute(step_id, label, args, python_code=False):
            actual = [sys.executable, "-B", "-c", args] if python_code else [sys.executable, "-B", str(CLI), *args]
            command = ["python3", "-c", args] if python_code else ["cortex", *args]
            result = subprocess.run(actual, cwd=project, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=15)
            require(result.returncode == 0, f"{step_id} failed: {result.stderr}")
            step = {"id": step_id, "label": label, "command": command,
                    "stdout": result.stdout, "stderr": result.stderr,
                    "exit_code": result.returncode}
            steps.append(step)
            return result

        hint = execute("hint", "Start with an empty history", ["hint", TASK, "--class", "build"])
        require("cortex log is empty" in hint.stdout, "Expected a clean, empty demo log")
        execute("log", "Record the scripted route", ["log-line", ROUTE, TASK, "--class", "build",
                "--tier-reason", REASON, "--project", "cortex-demo"])
        log = state / "cortex-log.jsonl"
        original = log.read_bytes()
        rows = [json.loads(line) for line in original.splitlines()]
        require(len(rows) == 1, "Logging must create exactly one route")
        route = rows[0]
        require(all(route.get(key) == value for key, value in {
            "event": "route", "task": TASK, "system": "Direct", "pattern": "cli-walkthrough",
            "tier": "L2", "tier_reason": REASON, "class": "build", "outcome": None,
            "project_ref": str(project.resolve()), "model": None,
        }.items()), "Recorded route differs from the declared walkthrough")
        event_id = route["event_id"]
        require(bool(re.fullmatch(r"[a-z]+_[a-f0-9]+", event_id)), "Expected an exact route event ID")
        substitutions[event_id] = "<route-id>"
        reference = execute("reference", "Read the exact route ID from the isolated log", READ_ID, python_code=True)
        require(reference.stdout.strip() == event_id, "Extracted route ID must match the verified record")
        before = execute("before", "Inspect the route before completion", ["show", "--last", "1"])
        require(ROUTE in before.stdout and "[SHIPPED]" not in before.stdout,
                "The saved route must be visible and unfinished before recording its outcome")
        # The route is now verified. This outcome refers only to this walkthrough.
        execute("outcome", "Complete the CLI walkthrough", ["outcome", "shipped", "--ref", event_id,
                "--note", NOTE])
        updated = log.read_bytes()
        final_rows = [json.loads(line) for line in updated.splitlines()]
        require(updated.startswith(original) and len(final_rows) == 2,
                "Outcome must append one event without rewriting the route")
        require(final_rows[1].get("event") == "outcome" and final_rows[1].get("ref") == event_id
                and final_rows[1].get("outcome") == "shipped" and final_rows[1].get("outcome_note") == NOTE,
                "Outcome must reference the exact verified route")
        after = execute("show", "Review the recorded outcome", ["show", "--last", "1"])
        require("[SHIPPED]" in after.stdout and ROUTE in after.stdout, "show must display the saved outcome")
        history = execute("history", "Inspect the append-only event history", ["history", event_id])
        require("corrections (1, oldest first)" in history.stdout and NOTE in history.stdout,
                "history must show the real outcome event and its scope note")
        for step in steps:
            step["command"] = [normalized(arg) for arg in step["command"]]
            step["stdout"] = normalized(step["stdout"])
            step["stderr"] = normalized(step["stderr"])
        return {
            "schema_version": 1,
            "kind": "scripted_cli_walkthrough",
            "disclosure": DISCLOSURE,
            "task": TASK,
            "route": ROUTE,
            "outcome_scope": NOTE,
            "cli_sha256": hashlib.sha256(CLI.read_bytes()).hexdigest(),
            "command_alias": "cortex = the running Python interpreter plus <repo>/bin/cortex",
            "normalization": {
                "<route-id>": "The exact generated route event ID, substituted consistently in commands and output",
                "<run-id>": "Generated CLI invocation ID",
                "<process-session>": "Parent-process fallback identity; no agent session is inherited",
                "<demo-project>": "Canonical disposable project directory",
                "<time>": "UTC date and minute printed by the CLI",
            },
            "checks": ["fresh history", "declared route persisted", "exact event reference",
                       "route visible before outcome", "outcome appended without rewriting route",
                       "show and history reflect walkthrough completion"],
            "steps": steps,
        }


def render_gif(capture):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("GIF export needs optional Pillow; --check and JSON capture use only the stdlib") from exc
    # Font files are optional rendering inputs only, never CLI dependencies.
    def font(size, bold=False):
        name = "Arial Bold.ttf" if bold else "Arial.ttf"
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            for path in (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else
                         ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
                if Path(path).is_file():
                    return ImageFont.truetype(path, size)
            raise RuntimeError("GIF export requires Arial or DejaVu Sans for readable text")

    steps = {step["id"]: step for step in capture["steps"]}
    frames = []
    ids = ["hint", "log", "before", "outcome", "show", "history"]
    durations = [4500, 6000, 4500, 5000, 5000, 6500]
    for number, step_id in enumerate(ids, 1):
        step = steps[step_id]
        frame = Image.new("RGB", (1100, 700), "#121018")
        draw = ImageDraw.Draw(frame)
        draw.rectangle((46, 41, 54, 84), fill="#8B5CF6")
        draw.text((72, 39), "Cortex in the CLI", font=font(34, True), fill="#F1EDF8")
        draw.text((46, 102), DISCLOSURE, font=font(20), fill="#C4B5FD")
        draw.line((46, 143, 1054, 143), fill="#3B304F", width=1)
        draw.text((46, 170), step["label"], font=font(28, True), fill="#F1EDF8")
        draw.text((1054, 175), f"{number} / {len(ids)}", anchor="ra", font=font(20), fill="#B7ACC9")
        command = "$ " + shlex.join(step["command"])
        # Wrapping changes presentation only; the capture preserves exact lines.
        command_lines = textwrap.wrap(command, width=89, subsequent_indent="  ",
                                      break_long_words=False, break_on_hyphens=False)
        y = 231
        for line in command_lines:
            draw.text((46, y), line, font=font(20), fill="#C4B5FD")
            y += 29
        y += 18
        output = step["stdout"] + step["stderr"]
        for line in output.splitlines():
            for wrapped in textwrap.wrap(line, width=97, replace_whitespace=False,
                                         break_long_words=False, break_on_hyphens=False) or [""]:
                draw.text((46, y), wrapped, font=font(20), fill="#F1EDF8")
                y += 29
        require(y < 606, f"Frame {step_id} overflows; shorten layout or split the captured output")
        draw.line((46, 620, 1054, 620), fill="#3B304F", width=1)
        draw.text((46, 643), '“shipped” means this walkthrough completed. No software changed.',
                  font=font(18), fill="#B7ACC9")
        draw.text((1054, 673), "IDs, times and temporary paths normalized · github.com/amitvijapur/cortex",
                  anchor="ra", font=font(16), fill="#B7ACC9")
        frames.append(frame)
    frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, optimize=False, disposal=2)
    require(GIF.stat().st_size < 2_000_000, "Demo GIF must remain below 2 MB")
    print(f"Wrote {GIF.relative_to(ROOT)}: 1100 × 700, {len(frames)} frames, "
          f"{sum(durations) / 1000:g}s, {GIF.stat().st_size:,} bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="replay and verify without writing the historical capture")
    parser.add_argument("--gif", action="store_true", help="also render the captured real output with optional Pillow")
    args = parser.parse_args()
    require(not (args.check and args.gif), "Use --check or --gif separately")
    observed = replay()
    if args.check:
        saved = json.loads(CAPTURE.read_text())
        # Nondeterministic provenance is normalized consistently. This checks the
        # accepted captured contract, not historical timestamp or random-ID bytes.
        for field in ("schema_version", "kind", "disclosure", "task", "route", "outcome_scope",
                      "normalization", "checks", "steps"):
            require(saved.get(field) == observed.get(field), f"Captured {field} differs from the current CLI contract")
        print("CLI walkthrough verified: 7 real commands; isolated route and append-only outcome; capture contract current.")
        return
    CAPTURE.parent.mkdir(exist_ok=True)
    CAPTURE.write_text(json.dumps(observed, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {CAPTURE.relative_to(ROOT)} from 7 real subprocess commands in disposable state.")
    if args.gif:
        render_gif(observed)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        print(f"demo error: {error}", file=sys.stderr)
        sys.exit(1)
