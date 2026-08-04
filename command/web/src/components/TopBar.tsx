// Cortex Command — sticky top bar: logomark, nav (Chat/Runs), CostTicker,
// live dot (WS state), and a pending-approval badge that scrolls to the card.

import type { ConnectionState } from "../lib/store";
import { cx } from "../lib/format";
import { Logomark } from "./Logomark";
import { CostTicker } from "./CostTicker";

export type View = "chat" | "runs";

const LIVE_LABEL: Record<ConnectionState, string> = {
  connecting: "CONN",
  open: "LIVE",
  stale: "STALE",
  down: "DOWN",
};

function livedotClass(c: ConnectionState): string {
  if (c === "open") return "livedot";
  if (c === "stale") return "livedot stale";
  return "livedot down";
}

export function TopBar(props: {
  view: View;
  onView: (v: View) => void;
  connection: ConnectionState;
  cost: number;
  pendingCount: number;
  onPendingClick: () => void;
}): React.ReactNode {
  const { view, onView, connection, cost, pendingCount, onPendingClick } = props;
  return (
    <header>
      <div className="wrap">
        <div className="head-in">
          <div className="brand">
            <Logomark />
            <span className="wordmark">Cortex Command</span>
            <span className="tagline">chat &middot; runs</span>
          </div>

          <nav className="topnav">
            <button
              className={cx("tab", view === "chat" && "active")}
              onClick={() => onView("chat")}
            >
              Chat
            </button>
            <button
              className={cx("tab", view === "runs" && "active")}
              onClick={() => onView("runs")}
            >
              Runs
            </button>
          </nav>

          <div className="topbar-right">
            {pendingCount > 0 && (
              <button
                className="approval-badge"
                onClick={onPendingClick}
                title="Jump to the pending approval"
              >
                <span className="ab-dot" />
                {pendingCount} pending
              </button>
            )}
            <CostTicker cost={cost} />
            <div className="live">
              <span className={livedotClass(connection)} />
              <span className="live-label">{LIVE_LABEL[connection]}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
