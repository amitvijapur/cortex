#!/usr/bin/env python3
"""Cortex intake worker — runs headless `claude -p` jobs and reports to Telegram.

  worker.py review <inbox_id>   fetch + judge the link, post a verdict + buttons
  worker.py build  <inbox_id>   apply the approved plan (edit cortex.md + install)

Spawned detached by bot.py so the poll loop never blocks. Verdict and build
results are exchanged with claude via JSON files (robust vs stdout parsing).
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import common as C

REVIEW_TIMEOUT = 360    # seconds
BUILD_TIMEOUT = 1200
REVIEW_MODEL = "sonnet"                    # cheaper; judging a skill doesn't need Opus
REVIEW_TOOLS = ["WebFetch", "Read", "Write", "Grep", "Glob"]
# Build edits the registry doc only — no Bash, no shell, no install execution.
BUILD_TOOLS = ["Edit", "Read", "Write", "Grep", "Glob"]
# Ask answers a freeform question — read-only, no edits, no shell.
ASK_TOOLS = ["WebFetch", "Read", "Grep", "Glob"]


def run_claude(prompt, allowed_tools=None, model=None, timeout=360):
    # Always scoped: bypassPermissions removes prompts but --allowedTools bounds
    # what the run can touch. Skip-permissions is intentionally not available here.
    cmd = [C.find_claude(), "-p", prompt, "--output-format", "json",
           "--permission-mode", "bypassPermissions"]
    if allowed_tools:
        cmd += ["--allowedTools", *allowed_tools]
    if model:
        cmd += ["--model", model]
    C.log(f"claude run: scoped model={model} tools={allowed_tools}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, cwd=str(C.HERE), env=C.claude_env())
    except subprocess.TimeoutExpired:
        C.log("claude run timed out")
        return None, "timeout"
    if proc.returncode != 0:
        C.log(f"claude exit {proc.returncode}: {proc.stderr[:400]}")
        return None, f"exit {proc.returncode}"
    return proc.stdout, None


# ── Shared formatting ───────────────────────────────────────────────────────

def _as_text(value):
    """Coerce a verdict field to a display string. The model sometimes returns
    summary/slots as a list of lines instead of a string — handle both."""
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return "" if value is None else str(value)


def verdict_message(entry_id, entry, verdict):
    rec = _as_text(verdict.get("recommendation", "?")).strip().lower()
    emoji = {"add": "✅", "maybe": "\U0001F914", "skip": "\U0001F6AB"}.get(rec, "•")
    title = _as_text(verdict.get("title")).strip() or entry.get("url", "")
    summary = _as_text(verdict.get("summary")).strip()
    slots = _as_text(verdict.get("slots_into")).strip()
    msg = f"{emoji} {rec.upper()} — {title}"
    if summary:
        msg += f"\n\n{summary}"
    if slots:
        msg += f"\n\n↳ fits: {slots}"
    msg += f"\n\nid: {entry_id}"
    return msg


# ── Review ──────────────────────────────────────────────────────────────────

def review_prompt(entry):
    vpath = C.VERDICTS_DIR / f"{entry['id']}.json"
    return f"""You are the Cortex intake reviewer. A link was dropped for possible addition to the user's Cortex routing framework (a meta-router over their workflow systems).

Item id: {entry['id']}
URL: {entry.get('url', '')}
Note from the user: {entry.get('note', '') or '(none)'}

Steps:
1. Fetch and read the URL with WebFetch. Determine exactly what it is: a Claude skill, an OMC/GSD workflow, an MCP server, an agent, a design system, a domain model, a library, or something else.
2. Read the user's registry at {C.CLAUDE_MD}. Decide honestly whether this adds a capability Cortex is missing or duplicates something already registered. Name any overlap explicitly. Be skeptical: the goal is to protect the registry from bloat, not to say yes.
3. Choose a recommendation: "add", "maybe" (worth a trial first), or "skip".
4. If add or maybe, write a concrete, runnable integration plan: the exact cortex.md registry entry and Decision Shortcut row to add, plus any install/setup commands (for example `claude plugin install X`, a git clone, or npm install).
5. If add or maybe, write a proposal note into {C.PROPOSALS_DIR} named "{entry['id']}-<short-slug>.md" with YAML frontmatter (tags: [cortex, proposal, intake], status: pending, source_url: the URL).

Finally, WRITE your verdict as JSON to exactly this path: {vpath}
Required keys:
  "recommendation": "add" | "maybe" | "skip"
  "title": short name of the thing
  "kind": what type it is
  "summary": 3 to 5 SHORT lines for a phone screen — what it is, and why add or skip
  "slots_into": which registry section / Decision Shortcut it fits, or "" if skip
  "plan": array of concrete integration steps (cortex.md edit + any commands), or [] if skip
  "proposal_path": absolute path to the note you wrote, or ""

The verdict file is the only output that matters."""


def do_review(entry_id):
    token = C.load_token()
    entry = C.get_entry(entry_id)
    if not entry:
        C.log(f"review: no entry {entry_id}")
        return 1
    chat_id = entry.get("chat_id")
    C.update_entry(entry_id, status="reviewing")

    vpath = C.VERDICTS_DIR / f"{entry_id}.json"
    if vpath.exists():
        vpath.unlink()

    _, err = run_claude(review_prompt(entry), allowed_tools=REVIEW_TOOLS,
                        model=REVIEW_MODEL, timeout=REVIEW_TIMEOUT)

    verdict = None
    if vpath.exists():
        try:
            verdict = json.loads(vpath.read_text())
        except Exception as exc:  # noqa: BLE001
            C.log(f"verdict parse error: {exc}")

    if not verdict:
        C.update_entry(entry_id, status="failed", verdict={"error": err or "no verdict file"})
        C.tg_send(token, chat_id,
                  f"⚠️ Couldn't review {entry_id} ({err or 'no verdict'}). "
                  f"Run /cortex-intake in a session to handle it.")
        return 1

    C.update_entry(entry_id, status="reviewed", verdict=verdict, reviewed_ts=C.now_iso())
    C.tg_send(token, chat_id, verdict_message(entry_id, entry, verdict),
              buttons=C.decision_keyboard(entry_id))
    return 0


# ── Build ───────────────────────────────────────────────────────────────────

def build_prompt(entry, verdict):
    rpath = C.RESULTS_DIR / f"{entry['id']}.json"
    plan = verdict.get("plan", [])
    return f"""You are the Cortex intake builder. The user approved adding this item to their Cortex framework. Your job is ONLY to update the registry documentation. You have no shell access and must not attempt to install anything.

Item id: {entry['id']}
URL: {entry.get('url', '')}
What it is: {verdict.get('title', '')} ({verdict.get('kind', '')})
Approved plan:
{json.dumps(plan, indent=2)}

Steps:
1. Edit {C.CLAUDE_MD} to add the registry entry and any Decision Shortcut row from the plan. A backup already exists, so edit the live file. Keep the change minimal and scoped to this one addition. Do not refactor unrelated parts, and make sure the file still reads as valid markdown.
2. Do NOT run any install or setup commands. You have no Bash tool and must not try. Instead, collect every install/setup command from the plan verbatim (plugin install, git clone, npm, etc.) so the user can run them.

Finally, WRITE a result JSON to exactly this path: {rpath}
Required keys:
  "applied": true | false          (did you successfully edit cortex.md?)
  "cortex_edit": one-line summary of what you added to cortex.md
  "install_commands": array of the exact shell commands the user still needs to run, or [] if none
  "notes": anything the user should know
  "needs_followup": "" or a short description of any other manual step required

The result file is the only output that matters."""


def do_build(entry_id):
    token = C.load_token()
    entry = C.get_entry(entry_id)
    if not entry:
        C.log(f"build: no entry {entry_id}")
        return 1
    chat_id = entry.get("chat_id")
    verdict = entry.get("verdict") if isinstance(entry.get("verdict"), dict) else {}
    C.update_entry(entry_id, status="building")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = C.BACKUPS_DIR / f"cortex.md.{ts}.{entry_id}"
    try:
        backup.write_text(C.CLAUDE_MD.read_text())
        C.log(f"backed up cortex.md -> {backup.name}")
    except Exception as exc:  # noqa: BLE001
        C.log(f"backup failed: {exc}")

    rpath = C.RESULTS_DIR / f"{entry_id}.json"
    if rpath.exists():
        rpath.unlink()

    _, err = run_claude(build_prompt(entry, verdict), allowed_tools=BUILD_TOOLS,
                        timeout=BUILD_TIMEOUT)

    result = None
    if rpath.exists():
        try:
            result = json.loads(rpath.read_text())
        except Exception as exc:  # noqa: BLE001
            C.log(f"result parse error: {exc}")

    if not result or not result.get("applied"):
        C.update_entry(entry_id, status="failed", build_result=result or {"error": err})
        detail = (result or {}).get("notes") or err or "unknown error"
        C.tg_send(token, chat_id,
                  f"⚠️ Build failed for {entry_id}. {detail}\n"
                  f"cortex.md backup: {backup.name}\nRun /cortex-intake in a session to finish.")
        return 1

    C.update_entry(entry_id, status="integrated", build_result=result, resolved_ts=C.now_iso())
    installs = result.get("install_commands") or []
    msg = f"✅ Added to Cortex — {result.get('cortex_edit', 'updated cortex.md')}"
    if installs:
        label = _as_text((entry.get("verdict") or {}).get("title")).strip() or entry.get("url", "") or entry_id
        C.add_install(label, installs, source_id=entry_id, note=result.get("needs_followup", ""))
        shown = "\n".join(f"  {c}" for c in installs[:8])
        msg += (f"\n\n📋 Queued {len(installs)} install step(s) for '{label}'.\n{shown}"
                f"\n\nNext laptop session, say 'clear list' and I'll run them.")
    if result.get("needs_followup"):
        msg += f"\n\n⚠️ Follow-up: {result['needs_followup']}"
    msg += f"\n\nbackup: {backup.name}"
    C.tg_send(token, chat_id, msg)
    return 0


# ── Ask (freeform prompt, no link) ──────────────────────────────────────────

def ask_prompt(entry):
    apath = C.ANSWERS_DIR / f"{entry['id']}.json"
    return f"""You are the user's Cortex assistant, replying to a message they sent through Telegram. Keep the answer concise and phone-friendly (a few short lines). You have READ-ONLY tools (WebFetch, Read, Grep, Glob): you cannot edit files, install anything, or run shell commands.

Message:
{entry.get('note', '')}

You may consult:
- Your Cortex registry / routing doc: {C.CLAUDE_MD}
- Your installed agent catalog: ~/.claude/agents/
- The intake inbox: {C.INBOX_PATH}
- Prior review verdicts: {C.VERDICTS_DIR}

If the message refers to something in the intake queue (a link he dropped, a pending decision), read the relevant verdict or inbox row and answer from it. If it asks you to check a repo for changes, do your best with the read-only tools and state plainly what you could and could not verify.

Write your reply as JSON to exactly this path: {apath}
Keys:
  "answer": your concise reply for Telegram (a few short lines)
  "actions": array of concrete next steps the user could take (e.g. "drop <link>", "tap Add on in_xxxx"), or []
The answer file is the only output that matters."""


def do_ask(entry_id):
    token = C.load_token()
    entry = C.get_entry(entry_id)
    if not entry:
        C.log(f"ask: no entry {entry_id}")
        return 1
    chat_id = entry.get("chat_id")
    C.update_entry(entry_id, status="asking")

    apath = C.ANSWERS_DIR / f"{entry_id}.json"
    if apath.exists():
        apath.unlink()

    _, err = run_claude(ask_prompt(entry), allowed_tools=ASK_TOOLS,
                        model=REVIEW_MODEL, timeout=REVIEW_TIMEOUT)

    ans = None
    if apath.exists():
        try:
            ans = json.loads(apath.read_text())
        except Exception as exc:  # noqa: BLE001
            C.log(f"answer parse error: {exc}")

    if not ans:
        C.update_entry(entry_id, status="failed", answer={"error": err or "no answer file"})
        C.tg_send(token, chat_id, f"⚠️ Couldn't answer {entry_id} ({err or 'no answer'}).")
        return 1

    C.update_entry(entry_id, status="answered", answer=ans, resolved_ts=C.now_iso())
    text = _as_text(ans.get("answer")).strip() or "(no answer)"
    actions = ans.get("actions") or []
    msg = f"💬 {text}"
    if actions:
        msg += "\n\nNext:\n" + "\n".join(f"  • {_as_text(a)}" for a in actions[:6])
    C.tg_send(token, chat_id, msg)
    return 0


# ── Resend (re-post an existing verdict, e.g. after a crash) ─────────────────

def do_resend(entry_id):
    token = C.load_token()
    entry = C.get_entry(entry_id)
    if not entry:
        C.log(f"resend: no entry {entry_id}")
        return 1
    verdict = entry.get("verdict")
    if not isinstance(verdict, dict):
        vpath = C.VERDICTS_DIR / f"{entry_id}.json"
        if vpath.exists():
            try:
                verdict = json.loads(vpath.read_text())
            except Exception:  # noqa: BLE001
                verdict = None
    if not isinstance(verdict, dict):
        C.tg_send(token, entry.get("chat_id"),
                  f"⚠️ No stored verdict for {entry_id}; drop the link again to re-review.")
        return 1
    C.update_entry(entry_id, status="reviewed", verdict=verdict)
    C.tg_send(token, entry.get("chat_id"), verdict_message(entry_id, entry, verdict),
              buttons=C.decision_keyboard(entry_id))
    return 0


# ── Install (the ONLY shell-capable path) ───────────────────────────────────
# Runs the exact commands stored for a queue id, verbatim. It takes only the
# queue id from the caller/callback, never shell text. There is no claude / LLM
# invocation here at all, so nothing is generated at run time and
# --dangerously-skip-permissions never applies. This is the single component
# with shell access; review/build/ask stay read-only or edit-only.

INSTALL_TIMEOUT = 1200

# Commands matching any of these are refused for auto-run. Defence in depth: the
# queued commands are already user-reviewed on the button, this catches an
# obvious poisoned entry before it runs.
DANGER_PATTERNS = [
    r"\brm\s+-[rf]*f[rf]*\s+(?:-[a-z]+\s+)*/(?:\s|$)",
    r"\brm\s+-[rf]*f[rf]*\s+(?:-[a-z]+\s+)*~(?:/\s*|\s|$)",
    r"\brm\s+-[rf]*f[rf]*\s+(?:-[a-z]+\s+)*\*",
    r":\(\)\s*\{\s*:\s*\|\s*:",
    r"\bmkfs\b", r"\bdd\s+if=", r">\s*/dev/(?:sd|disk|zero|random)",
    r"\bsudo\b", r"\bdoas\b",
    r"\bchmod\s+-R?\s*0?777\s+/",
    r"(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|d)?sh\b",
    r"\beval\b[^\n]*\$\(\s*(?:curl|wget)",
    r"\bnc\b[^\n]*\s-e\b",
    r">\s*~?/?\.?(?:zshrc|bashrc|zprofile|bash_profile|zshenv)\b",
]


def is_dangerous(command):
    return any(re.search(p, command, re.IGNORECASE) for p in DANGER_PATTERNS)


def run_shell(command, timeout=INSTALL_TIMEOUT):
    """Run one command string in the user's login shell (so PATH, uv, git, node
    resolve) from HOME. Returns (returncode, combined_output)."""
    env = C.claude_env()
    extra = os.pathsep.join([
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin", "/usr/local/bin", "/opt/anaconda3/bin",
    ])
    env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(["/bin/zsh", "-lc", command],
                              cwd=str(Path.home()), capture_output=True, text=True,
                              timeout=timeout, env=env)
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return 1, f"failed to launch: {exc}"


def do_install(iq_id, chat_id):
    token = C.load_token()
    item = C.get_install(iq_id)
    if not item:
        C.tg_send(token, chat_id, f"⚠️ install {iq_id} not found in the queue")
        return 1
    if item.get("status") != "pending":
        C.tg_send(token, chat_id, f"install {iq_id} is already {item.get('status')}")
        return 0

    commands = item.get("commands", [])   # the ONLY commands that run — verbatim
    label = item.get("label", iq_id)

    flagged = [c for c in commands if is_dangerous(c)]
    if flagged:
        shown = "\n".join(f"  {c}" for c in flagged)
        C.tg_send(token, chat_id,
                  f"🛑 Refusing to auto-run '{label}'. A command looks dangerous:\n{shown}\n"
                  f"Left in the queue. Run it yourself in a session if you're sure.")
        C.log(f"install {iq_id} refused: dangerous pattern")
        return 1

    C.log(f"installing {iq_id}: {label} ({len(commands)} cmd)")
    ran, failed = [], None
    for cmd in commands:
        code, out = run_shell(cmd)
        C.log(f"  [{code}] {cmd}")
        ran.append((cmd, code))
        if code != 0:
            failed = (cmd, code, out)
            break  # stop on first failure; leave item pending for retry

    if failed:
        cmd, code, out = failed
        tail = (out or "")[-600:]
        C.tg_send(token, chat_id,
                  f"⚠️ Install failed: {label}\nFailing command (exit {code}):\n  {cmd}\n\n{tail}\n\n"
                  f"Left in the queue — fix and tap again, or run it in a session.")
        return 1

    C.set_install_status(iq_id, "done")
    done = "\n".join(f"  ✓ {c}" for c, _ in ran)
    C.tg_send(token, chat_id, f"✅ Installed: {label}\n\n{done}")
    return 0


def main():
    argv = sys.argv
    if len(argv) < 3 or argv[1] not in ("review", "build", "ask", "resend", "install"):
        print("usage: worker.py <review|build|ask|resend|install> <id> [chat_id]", file=sys.stderr)
        return 2
    mode, item_id = argv[1], argv[2]
    chat_id = argv[3] if len(argv) > 3 else C.DEFAULT_CHAT_ID
    try:
        if mode == "review":
            return do_review(item_id)
        if mode == "build":
            return do_build(item_id)
        if mode == "ask":
            return do_ask(item_id)
        if mode == "resend":
            return do_resend(item_id)
        return do_install(item_id, chat_id)
    except Exception as exc:  # noqa: BLE001
        C.log(f"worker {mode} crashed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
