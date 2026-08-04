// Cortex Command — App shell. Wires the store, the active Client (WS or demo),
// the TopBar, and the Chat/Runs views. On first load with no session it shows
// the ProjectPicker; ?demo=1 swaps in the canned DemoClient and skips the picker.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  readState,
  selectFirstPendingApprovalId,
  selectPendingApprovalCount,
  selectSession,
  selectTotalCost,
  seedSession,
  useStore,
} from "./lib/store";
import { WsClient, type Client } from "./lib/ws";
import { api, ApiError, type HistoryEntry } from "./lib/api";
import { ClientContext } from "./components/ClientContext";
import { TopBar, type View } from "./components/TopBar";
import { ChatView } from "./components/ChatView";
import { RunsView } from "./components/RunsView";
import { ProjectPicker, pushRecent } from "./components/ProjectPicker";
import { DemoClient } from "./dev/demo";

const DEMO = new URLSearchParams(window.location.search).has("demo");
const DEMO_KEY = "sess_demo01";

export function App(): React.ReactNode {
  const [view, setView] = useState<View>("chat");
  const [activeKey, setActiveKey] = useState<string | null>(DEMO ? DEMO_KEY : null);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  // The client is created once for the lifetime of the app.
  const client: Client = useMemo(() => {
    return DEMO ? new DemoClient() : new WsClient();
  }, []);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    if (client instanceof DemoClient) client.start();
    else if (client instanceof WsClient) client.connect();
    return () => {
      if (client instanceof WsClient) client.dispose();
    };
  }, [client]);

  const connection = useStore((s) => s.connection);
  const totalCost = useStore(selectTotalCost);
  const pendingCount = useStore(selectPendingApprovalCount);
  const sessionKeys = useStore((s) => Object.keys(s.sessions).join(","));
  const activeSession = useStore(selectSession(activeKey));

  // Auto-select the first known session when we don't have one yet.
  useEffect(() => {
    if (DEMO || activeKey) return;
    const keys = readState().sessions;
    const first = Object.keys(keys)[0];
    if (first) setActiveKey(first);
  }, [sessionKeys, activeKey]);

  // Attach to an already-active session (e.g. after a 409, or explicit resume).
  // Hydrate its meta via GET /api/sessions/:key so ChatView renders immediately,
  // then subscribe from our current lastSeq (replay reconciles the transcript;
  // detail.pendingApprovals is available as a belt-and-braces cross-check).
  const attachToSession = useCallback(
    async (key: string, cwd?: string) => {
      try {
        const detail = await api.getSession(key);
        seedSession(detail.meta);
      } catch {
        /* store may already hold it from hello; replay will reconcile */
      }
      const cur = readState().sessions[key];
      if (client instanceof WsClient) client.subscribeSession(key, cur ? cur.lastSeq : 0);
      if (cwd) pushRecent(cwd);
      setActiveKey(key);
      setView("chat");
    },
    [client],
  );

  const openProject = useCallback(
    async (cwd: string, resumeSdkSessionId?: string) => {
      setOpening(true);
      setOpenError(null);
      try {
        const meta = await api.createSession({ cwd, kind: "chat", resumeSdkSessionId });
        seedSession(meta);
        if (client instanceof WsClient) client.subscribeSession(meta.sessionKey, 0);
        pushRecent(cwd);
        setActiveKey(meta.sessionKey);
        setView("chat");
      } catch (e) {
        // M1 caps chat sessions at 1. A 409 means one is already alive (the normal
        // path when the browser is reopened) — attach to it instead of erroring.
        if (e instanceof ApiError && e.status === 409) {
          const key = (e.body as { sessionKey?: string } | undefined)?.sessionKey;
          if (key) {
            await attachToSession(key, cwd);
            return;
          }
        }
        setOpenError(e instanceof Error ? e.message : "failed to open project");
      } finally {
        setOpening(false);
      }
    },
    [client, attachToSession],
  );

  const onResume = useCallback(
    (entry: HistoryEntry) => {
      void openProject(entry.cwd, entry.sdkSessionId);
    },
    [openProject],
  );

  const scrollToPending = useCallback(() => {
    const id = selectFirstPendingApprovalId(readState());
    if (!id) return;
    const el = document.getElementById("approval-" + id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  return (
    <ClientContext.Provider value={client}>
      <TopBar
        view={view}
        onView={setView}
        connection={connection}
        cost={totalCost}
        pendingCount={pendingCount}
        onPendingClick={scrollToPending}
      />
      <main className="app-main">
        {view === "runs" ? (
          <RunsView />
        ) : activeSession ? (
          <ChatView session={activeSession} onResume={onResume} />
        ) : (
          <ProjectPicker
            onPick={(cwd) => void openProject(cwd)}
            busy={opening}
            error={openError}
          />
        )}
      </main>
    </ClientContext.Provider>
  );
}
