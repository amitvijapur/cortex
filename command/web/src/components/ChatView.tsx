// Cortex Command — ChatView: SessionHeader (cwd / sdk id / status / Interrupt /
// history toggle), the Transcript, and the Composer. Auto-scrolls to the newest
// content unless the user has scrolled up.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { SessionState } from "../lib/store";
import type { SessionStatus } from "@cortex-command/shared";
import type { HistoryEntry } from "../lib/api";
import { cx, shortCwd, truncId } from "../lib/format";
import { useClient } from "./ClientContext";
import { Transcript } from "./Transcript";
import { Composer } from "./Composer";
import { SessionDrawer } from "./SessionDrawer";

const STATUS_LABEL: Record<SessionStatus, string> = {
  starting: "starting",
  running: "running",
  idle: "idle",
  awaiting_permission: "awaiting approval",
  completed: "completed",
  error: "error",
  disposed: "disposed",
};

function statusClass(s: SessionStatus): string {
  if (s === "running") return "sc-running";
  if (s === "awaiting_permission") return "sc-await";
  if (s === "error") return "sc-error";
  if (s === "completed" || s === "disposed") return "sc-done";
  return "sc-idle";
}

export function ChatView({
  session,
  onResume,
}: {
  session: SessionState;
  onResume: (entry: HistoryEntry) => void;
}): React.ReactNode {
  const client = useClient();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [resumeBusy, setResumeBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickRef = useRef(true);

  const { meta, status } = session;
  const canInterrupt = status === "running" || status === "awaiting_permission";

  // Track whether the user is pinned to the bottom.
  function onScroll(): void {
    const el = scrollRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickRef.current = dist < 80;
  }

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [session.blocks, session.approvals]);

  async function handleResume(entry: HistoryEntry): Promise<void> {
    setResumeBusy(true);
    try {
      await Promise.resolve(onResume(entry));
    } finally {
      setResumeBusy(false);
      setDrawerOpen(false);
    }
  }

  return (
    <div className="chatview">
      <div className="session-header">
        <div className="sh-left">
          <span className="sh-cwd mono" title={meta.cwd}>
            {shortCwd(meta.cwd)}
          </span>
          <span className="sh-sdk mono" title={meta.sdkSessionId ?? "no sdk session yet"}>
            {truncId(meta.sdkSessionId)}
          </span>
          {meta.model && <span className="sh-model mono">{meta.model}</span>}
        </div>
        <div className="sh-right">
          <span className={cx("status-chip mono", statusClass(status))}>
            {STATUS_LABEL[status]}
          </span>
          <button
            className="sh-btn"
            disabled={!canInterrupt}
            onClick={() => client.sendInterrupt(meta.sessionKey)}
          >
            Interrupt
          </button>
          <button className="sh-btn" onClick={() => setDrawerOpen(true)}>
            History
          </button>
        </div>
      </div>

      <div className="transcript-scroll" ref={scrollRef} onScroll={onScroll}>
        <div className="wrap transcript-wrap">
          {session.error && <div className="session-error mono">{session.error}</div>}
          <Transcript session={session} />
        </div>
      </div>

      <div className="composer-dock">
        <div className="wrap">
          <Composer sessionKey={meta.sessionKey} status={status} />
        </div>
      </div>

      <SessionDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onResume={(e) => void handleResume(e)}
        busy={resumeBusy}
      />
    </div>
  );
}
