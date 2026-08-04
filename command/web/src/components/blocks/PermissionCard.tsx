// Cortex Command — PermissionCard, rendered inline at the tool's position.
//
// Pending: amber left border, tool chip, command codeblock, Approve (solid
// green) / Deny (solid red), and a live countdown to the absolute expiresAt
// (survives reconnect — the reducer stores the server timestamp). Once resolved
// it collapses to a single chip row: "Approved by you · HH:MM" / "Denied" /
// "Auto-denied (timeout)".

import { useEffect, useState } from "react";
import type { PendingApproval } from "@cortex-command/shared";
import { fmtClock, fmtCountdown } from "../../lib/format";
import { serverToClient } from "../../lib/store";
import { useClient } from "../ClientContext";

function commandText(input: unknown): string | null {
  if (input && typeof input === "object") {
    const obj = input as Record<string, unknown>;
    if (typeof obj["command"] === "string") return obj["command"] as string;
  }
  return null;
}

function ResolvedRow({ approval }: { approval: PendingApproval }): React.ReactNode {
  const at = approval.resolvedBy ? fmtClock(Date.now()) : "";
  let label: string;
  let cls: string;
  if (approval.status === "approved") {
    label = "Approved by you" + (at ? " · " + at : "");
    cls = "resolved-approved";
  } else if (approval.status === "expired") {
    label = "Auto-denied (timeout)";
    cls = "resolved-timeout";
  } else {
    label = approval.resolvedBy === "timeout" ? "Auto-denied (timeout)" : "Denied";
    cls = "resolved-denied";
  }
  return (
    <div className={"perm-resolved " + cls}>
      <span className="perm-resolved-dot" />
      <span className="perm-resolved-label mono">{label}</span>
      {approval.note && <span className="perm-resolved-note">{approval.note}</span>}
    </div>
  );
}

export function PermissionCard({ approval }: { approval: PendingApproval }): React.ReactNode {
  const client = useClient();
  const [nowTick, setNowTick] = useState(Date.now());

  const pending = approval.status === "pending";

  useEffect(() => {
    if (!pending) return;
    const id = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [pending]);

  if (!pending) {
    return (
      <div className="perm-card resolved" id={"approval-" + approval.approvalId}>
        <ResolvedRow approval={approval} />
      </div>
    );
  }

  const expiresClient = serverToClient(approval.expiresAt);
  const remaining = expiresClient - nowTick;
  const cmd = commandText(approval.input);

  return (
    <div className="perm-card pending" id={"approval-" + approval.approvalId}>
      <div className="perm-head">
        <span className="perm-chip mono">{approval.toolName}</span>
        <span className="perm-ask mono">needs approval</span>
        <span className="perm-countdown mono" title="Auto-denies at expiry">
          {fmtCountdown(remaining)}
        </span>
      </div>
      {cmd && <pre className="codeblock perm-cmd">{cmd}</pre>}
      <div className="perm-actions">
        <button
          className="perm-btn perm-approve"
          onClick={() => client.sendPermissionDecision(approval.approvalId, "approve")}
        >
          Approve
        </button>
        <button
          className="perm-btn perm-deny"
          onClick={() => client.sendPermissionDecision(approval.approvalId, "deny")}
        >
          Deny
        </button>
      </div>
    </div>
  );
}
