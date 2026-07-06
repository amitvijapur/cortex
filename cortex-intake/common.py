"""Shared helpers for the Cortex intake bot and its workers.

Stdlib only. Holds the Telegram API wrapper, the inbox store, path config,
and the logic for locating and running headless `claude -p`.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_PATH = HERE / ".env"
OFFSET_PATH = HERE / ".offset"
LOGS_DIR = HERE / "logs"
VERDICTS_DIR = HERE / "verdicts"
RESULTS_DIR = HERE / "results"
ANSWERS_DIR = HERE / "answers"
BACKUPS_DIR = HERE / "backups"

# CLAUDE_DIR defaults to ~/.claude; override with the CLAUDE_DIR env var.
CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", Path.home() / ".claude"))
INBOX_PATH = CLAUDE_DIR / "cortex-inbox.jsonl"
CLAUDE_MD = CLAUDE_DIR / "cortex.md"

# Optional Obsidian surface for proposal notes; falls back to CLAUDE_DIR.
_OBSIDIAN = os.environ.get("CORTEX_OBSIDIAN_ROOT")
PROPOSALS_DIR = (Path(_OBSIDIAN) / "proposals") if _OBSIDIAN else (CLAUDE_DIR / "cortex-proposals")

# Telegram user ids allowed to talk to the bot, comma-separated in the env
# (e.g. CORTEX_INBOX_ALLOWED_IDS=12345678,87654321). Empty = the bot ignores everyone.
ALLOWED_IDS = {x.strip() for x in os.environ.get("CORTEX_INBOX_ALLOWED_IDS", "").split(",") if x.strip()}
# DM chat_id equals the user id; where worker-initiated messages go by default.
DEFAULT_CHAT_ID = os.environ.get("CORTEX_INBOX_DEFAULT_CHAT") or next(iter(ALLOWED_IDS), "")

for _d in (LOGS_DIR, VERDICTS_DIR, RESULTS_DIR, ANSWERS_DIR, BACKUPS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    sys.stderr.write(f"{now_iso()} {msg}\n")
    sys.stderr.flush()


def load_token():
    if not ENV_PATH.exists():
        raise SystemExit(f"missing {ENV_PATH}; set CORTEX_INBOX_BOT_TOKEN")
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() == "CORTEX_INBOX_BOT_TOKEN":
            val = val.strip().strip('"').strip("'")
            if val:
                return val
    raise SystemExit("CORTEX_INBOX_BOT_TOKEN empty or missing in .env")


# ── Headless claude location + env ──────────────────────────────────────────

def find_claude():
    found = shutil.which("claude")
    if found:
        return found
    # launchd PATH usually lacks the nvm bin; glob for it, newest first.
    cands = sorted(glob.glob(str(Path.home() / ".nvm/versions/node/*/bin/claude")), reverse=True)
    if cands:
        return cands[0]
    for cand in ("/usr/local/bin/claude", "/opt/homebrew/bin/claude"):
        if Path(cand).exists():
            return cand
    return "claude"


def claude_env():
    """os.environ plus the node/claude bin dir on PATH, so the claude shebang
    (which resolves `node`) works under the minimal launchd environment."""
    env = dict(os.environ)
    node_bin = str(Path(find_claude()).parent)
    env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    return env


# ── Telegram API ────────────────────────────────────────────────────────────

def api(token, method, params=None, timeout=60):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def decision_keyboard(entry_id):
    return json.dumps({
        "inline_keyboard": [[
            {"text": "✅ Add", "callback_data": f"add:{entry_id}"},
            {"text": "❌ Skip", "callback_data": f"skip:{entry_id}"},
        ]]
    })


def install_keyboard(iq_id):
    # callback data carries ONLY the queue id — never any shell text.
    return json.dumps({
        "inline_keyboard": [[
            {"text": "▶️ Confirm & run", "callback_data": f"irun:{iq_id}"},
            {"text": "⏭ Skip", "callback_data": f"iskip:{iq_id}"},
        ]]
    })


def tg_send(token, chat_id, text, buttons=None):
    if not chat_id:
        log("tg_send skipped: no chat_id")
        return None
    params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if buttons:
        params["reply_markup"] = buttons
    try:
        return api(token, "sendMessage", params)
    except Exception as exc:  # noqa: BLE001
        log(f"tg_send failed: {exc}")
        return None


def tg_edit(token, chat_id, message_id, text, buttons=None):
    params = {"chat_id": chat_id, "message_id": message_id,
              "text": text, "disable_web_page_preview": "true"}
    if buttons:
        params["reply_markup"] = buttons
    try:
        return api(token, "editMessageText", params)
    except Exception as exc:  # noqa: BLE001
        log(f"tg_edit failed: {exc}")
        return None


def tg_answer(token, callback_id, text=""):
    try:
        return api(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text})
    except Exception as exc:  # noqa: BLE001
        log(f"tg_answer failed: {exc}")
        return None


# ── Inbox store ─────────────────────────────────────────────────────────────

def read_inbox():
    if not INBOX_PATH.exists():
        return []
    out = []
    for line in INBOX_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def write_inbox(entries):
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_PATH.write_text("".join(json.dumps(e) + "\n" for e in entries))


def get_entry(entry_id):
    for entry in read_inbox():
        if entry.get("id") == entry_id:
            return entry
    return None


def update_entry(entry_id, **fields):
    entries = read_inbox()
    for entry in entries:
        if entry.get("id") == entry_id:
            entry.update(fields)
            write_inbox(entries)
            return entry
    return None


def new_id():
    seed = f"{now_iso()}{os.getpid()}{os.urandom(4).hex()}"
    return "in_" + hashlib.sha1(seed.encode()).hexdigest()[:8]


# ── Install queue ───────────────────────────────────────────────────────────
# Commands surfaced by a build (setup commands the user must run) live here until
# they are run via "clear list" in a writable session. Builds never run installs.

INSTALL_QUEUE_PATH = CLAUDE_DIR / "cortex-install-queue.jsonl"
CORTEX_BIN = CLAUDE_DIR / "bin" / "cortex"


def read_installs():
    if not INSTALL_QUEUE_PATH.exists():
        return []
    out = []
    for line in INSTALL_QUEUE_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def write_installs(entries):
    INSTALL_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSTALL_QUEUE_PATH.write_text("".join(json.dumps(e) + "\n" for e in entries))


def add_install(label, commands, source_id=None, note=""):
    entries = read_installs()
    # Don't double-queue the same source while it's still pending.
    for entry in entries:
        if source_id and entry.get("source_id") == source_id and entry.get("status") == "pending":
            return entry
    seed = f"{now_iso()}{os.getpid()}{os.urandom(4).hex()}"
    entry = {
        "id": "iq_" + hashlib.sha1(seed.encode()).hexdigest()[:8],
        "ts": now_iso(),
        "source_id": source_id,
        "label": label,
        "commands": list(commands),
        "note": note,
        "status": "pending",
        "done_ts": None,
    }
    entries.append(entry)
    write_installs(entries)
    return entry


def get_install(iq_id):
    for entry in read_installs():
        if entry.get("id") == iq_id:
            return entry
    return None


def set_install_status(iq_id, status):
    """Mark a queue item via the cortex CLI, the single source of truth for the
    mutation (`cortex installs done|skip <id>`)."""
    try:
        subprocess.run([sys.executable, str(CORTEX_BIN), "installs", status, iq_id],
                       capture_output=True, text=True, timeout=30)
    except Exception as exc:  # noqa: BLE001
        log(f"set_install_status {iq_id} {status} failed: {exc}")
