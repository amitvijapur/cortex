#!/usr/bin/env python3
"""Cortex intake bot — dedicated Telegram listener + orchestrator.

Captures dropped links, kicks off a headless review job per link, posts the
verdict back with Add / Skip buttons, and on approval kicks off a full build.
Stdlib only. All heavy work runs in detached worker.py subprocesses so this
poll loop never blocks. Runs under the com.example.cortex-intake launchd agent.
"""
import re
import subprocess
import sys
import time

import common as C

WORKER = C.HERE / "worker.py"
WORKER_LOG = C.LOGS_DIR / "worker.log"
URL_RE = re.compile(r"https?://[^\s]+")


def read_offset():
    try:
        return int(C.OFFSET_PATH.read_text().strip())
    except (OSError, ValueError):
        return 0


def write_offset(value):
    C.OFFSET_PATH.write_text(str(value))


def spawn(mode, entry_id, *extra):
    logf = open(WORKER_LOG, "a")
    subprocess.Popen(
        [sys.executable, str(WORKER), mode, entry_id, *extra],
        cwd=str(C.HERE), env=C.claude_env(),
        stdout=logf, stderr=logf, start_new_session=True,
    )
    C.log(f"spawned worker {mode} {entry_id} {' '.join(extra)}".rstrip())


def make_entry(url, note, frm, chat_id):
    return {
        "id": C.new_id(),
        "ts": C.now_iso(),
        "url": url,
        "note": note,
        "source": "telegram",
        "from": frm,
        "chat_id": chat_id,
        "status": "pending",
        "verdict": None,
        "resolved_ts": None,
    }


def append_entry(entry):
    entries = C.read_inbox()
    entries.append(entry)
    C.write_inbox(entries)


def post_installs(token, chat_id):
    pending = [e for e in C.read_installs() if e.get("status") == "pending"]
    if not pending:
        C.tg_send(token, chat_id, "No pending installs. 🎉")
        return
    C.tg_send(token, chat_id,
              f"You have {len(pending)} pending install(s). Read the commands, then tap Confirm to run them on your laptop.")
    for e in pending:
        cmds = "\n".join(e.get("commands", []))
        note = f"\n\n⚠️ {e['note']}" if e.get("note") else ""
        C.tg_send(token, chat_id,
                  f"📦 {e.get('label', '')}\n\n{cmds}{note}\n\nid: {e.get('id')}",
                  buttons=C.install_keyboard(e.get("id")))


def handle_message(token, msg):
    frm = str(msg.get("from", {}).get("id", ""))
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text") or msg.get("caption") or ""
    if frm not in C.ALLOWED_IDS:
        C.log(f"ignored message from unlisted id {frm!r}")
        return

    low = text.strip().lower()
    if low in ("/start", "/help"):
        C.tg_send(token, chat_id,
                  "Here's what you can do:\n"
                  "• Drop a link (skill, workflow, MCP, tool) and I review it against "
                  "Cortex, then send a verdict with Add / Skip buttons.\n"
                  "• Send /installs to see queued setup commands and run them with a tap.\n"
                  "• Or just ask me anything about your Cortex setup and I answer here.")
        return

    if low in ("/installs", "installs", "show installs", "run installs", "pending installs"):
        post_installs(token, chat_id)
        return

    urls = URL_RE.findall(text)
    note = URL_RE.sub("", text).strip()

    if urls:
        for raw in urls:
            url = raw.rstrip(".,);]")
            entry = make_entry(url, note, frm, chat_id)
            append_entry(entry)
            C.tg_send(token, chat_id, f"🔍 Reviewing {url}\n(id {entry['id']}, ~1 min)")
            spawn("review", entry["id"])
    elif text:
        entry = make_entry("", text, frm, chat_id)
        append_entry(entry)
        C.tg_send(token, chat_id, f"💬 On it… (id {entry['id']})")
        spawn("ask", entry["id"])


def handle_callback(token, cq):
    frm = str(cq.get("from", {}).get("id", ""))
    data = cq.get("data", "")
    cq_id = cq.get("id")
    msg = cq.get("message", {}) or {}
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if frm not in C.ALLOWED_IDS:
        C.tg_answer(token, cq_id, "not authorized")
        return

    action, _, item_id = data.partition(":")

    # Install-queue buttons — callback carries ONLY the queue id, never commands.
    # The install worker re-reads the stored commands for this id and runs those.
    if action in ("irun", "iskip"):
        item = C.get_install(item_id)
        if not item or item.get("status") != "pending":
            C.tg_answer(token, cq_id, "not pending")
            return
        if action == "irun":
            C.tg_answer(token, cq_id, "Running…")
            C.tg_edit(token, chat_id, message_id,
                      f"⏳ Running '{item.get('label', '')}' … I'll report back here.")
            spawn("install", item_id, str(chat_id))
        else:
            C.set_install_status(item_id, "skip")
            C.tg_answer(token, cq_id, "Skipped")
            C.tg_edit(token, chat_id, message_id, f"⏭ Skipped install {item_id}.")
        return

    # Inbox verdict buttons (add / skip).
    entry = C.get_entry(item_id)
    if not entry:
        C.tg_answer(token, cq_id, "unknown item")
        return

    status = entry.get("status")
    if status in ("building", "integrated"):
        C.tg_answer(token, cq_id, f"already {status}")
        return

    if action == "add":
        C.tg_answer(token, cq_id, "Adding…")
        C.tg_edit(token, chat_id, message_id, f"⏳ Adding {item_id} to Cortex … I'll confirm here when done.")
        spawn("build", item_id)
    elif action == "skip":
        C.tg_answer(token, cq_id, "Skipped")
        C.update_entry(item_id, status="rejected", resolved_ts=C.now_iso())
        C.tg_edit(token, chat_id, message_id, f"❌ Skipped {item_id}. Nothing added.")
    else:
        C.tg_answer(token, cq_id, "?")


def main():
    token = C.load_token()
    try:
        me = C.api(token, "getMe")
        C.log(f"cortex-intake bot online as @{me.get('result', {}).get('username', '?')}")
    except Exception as exc:  # noqa: BLE001
        C.log(f"getMe failed (bad token?): {exc}")

    offset = read_offset()
    while True:
        try:
            resp = C.api(token, "getUpdates", {
                "offset": offset,
                "timeout": 50,
                "allowed_updates": '["message","channel_post","callback_query"]',
            }, timeout=60)
        except Exception as exc:  # noqa: BLE001
            C.log(f"getUpdates error: {exc}")
            time.sleep(5)
            continue
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            write_offset(offset)
            try:
                if "callback_query" in upd:
                    handle_callback(token, upd["callback_query"])
                else:
                    message = upd.get("message") or upd.get("channel_post")
                    if message:
                        handle_message(token, message)
            except Exception as exc:  # noqa: BLE001 - never let one update kill the loop
                C.log(f"handler error: {exc}")


if __name__ == "__main__":
    main()
