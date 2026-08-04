// Cortex Command — Composer. Cmd/Ctrl+Enter sends. Effectively never hard-
// disabled: the SDK runtime only completes its handshake once the FIRST user
// message is pushed into the input queue, so a "starting" session MUST accept
// input — sending is what boots it. We only hard-disable for genuinely terminal
// sessions (disposed / error). A status-aware hint explains any delay: "queued —
// session is booting" during startup, "queued" while a turn is already in flight.

import { useRef, useState } from "react";
import type { SessionStatus } from "@cortex-command/shared";
import { useClient } from "./ClientContext";

let msgCounter = 0;

export function Composer({
  sessionKey,
  status,
}: {
  sessionKey: string;
  status: SessionStatus;
}): React.ReactNode {
  const client = useClient();
  const [text, setText] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const terminal = status === "disposed" || status === "error";
  const booting = status === "starting";
  const midTurn = status === "running" || status === "awaiting_permission";
  // Enabled whenever there's text and the session isn't dead. Never gated on
  // "starting" — that would deadlock a fresh session (it can't init without the
  // first message).
  const canSend = text.trim().length > 0 && !terminal;

  function send(): void {
    const t = text.trim();
    if (!t || terminal) return;
    const clientMsgId = "m" + Date.now() + "-" + msgCounter++;
    client.sendUserMessage(sessionKey, t, clientMsgId);
    setText("");
    taRef.current?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  }

  const hint = terminal
    ? "session ended"
    : booting
      ? "queued — session is booting"
      : midTurn
        ? "turn in flight — your message will be queued"
        : "⌘↵ to send";

  return (
    <div className="composer">
      <textarea
        ref={taRef}
        className="composer-input"
        placeholder={terminal ? "Session ended" : "Message Claude…  (⌘↵ to send)"}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={3}
        spellCheck={false}
        disabled={terminal}
      />
      <div className="composer-foot">
        <span className="composer-hint mono">{hint}</span>
        <button className="composer-send" onClick={send} disabled={!canSend}>
          {midTurn ? "Queue" : "Send"}
        </button>
      </div>
    </div>
  );
}
