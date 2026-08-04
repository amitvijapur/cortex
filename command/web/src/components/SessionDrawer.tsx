// Cortex Command — SessionDrawer: prior SDK sessions (GET /api/history) with a
// Resume button (POST /api/sessions with resumeSdkSessionId).

import { useEffect, useState } from "react";
import { api, type HistoryEntry } from "../lib/api";
import { ago, shortCwd, truncId } from "../lib/format";

export function SessionDrawer({
  open,
  onClose,
  onResume,
  busy,
}: {
  open: boolean;
  onClose: () => void;
  onResume: (entry: HistoryEntry) => void;
  busy: boolean;
}): React.ReactNode {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let live = true;
    setError(null);
    api
      .history()
      .then((h) => {
        if (live) setEntries(h);
      })
      .catch((e: unknown) => {
        if (live) setError(e instanceof Error ? e.message : "failed to load history");
      });
    return () => {
      live = false;
    };
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer">
        <div className="drawer-h">
          <span className="drawer-title mono">HISTORY</span>
          <button className="drawer-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="drawer-body">
          {error && <div className="drawer-error mono">{error}</div>}
          {!entries && !error && <div className="drawer-loading mono">loading…</div>}
          {entries && entries.length === 0 && (
            <div className="drawer-loading mono">no prior sessions</div>
          )}
          {entries?.map((e) => (
            <div className="hist-card" key={e.sdkSessionId}>
              <div className="hist-top">
                <span className="hist-cwd mono">{shortCwd(e.cwd)}</span>
                {typeof e.updatedAt === "number" && (
                  <span className="hist-time mono">{ago(e.updatedAt)}</span>
                )}
              </div>
              {e.title && <div className="hist-title">{e.title}</div>}
              <div className="hist-meta mono">
                <span>{truncId(e.sdkSessionId)}</span>
                {typeof e.messageCount === "number" && <span>{e.messageCount} msgs</span>}
              </div>
              <button
                className="hist-resume"
                disabled={busy}
                onClick={() => onResume(e)}
              >
                Resume
              </button>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
