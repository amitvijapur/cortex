// Cortex Command — PermissionBroker: the blocking approval gate.
//
// The SDK calls `canUseTool(name, input, { toolUseID, signal })` for every tool
// NOT covered by the profile's allowedTools. This broker turns that call into a
// PendingApproval that blocks on a promise until either an operator decides
// (over WS: permission.decide) or the profile's absolute timeout fires a
// default-deny. Both the request and its resolution are written to the session's
// EventLog, so a refresh / second tab reconstructs the card from replay; the
// live pending set is also exposed for GET /api/sessions/:key.
//
// Guarantees:
//  - idempotent decide (first resolution wins; later ones no-op → return false)
//  - absolute expiresAt (countdowns survive reconnects)
//  - abort (session interrupt/dispose) resolves as a timeout-style deny so the
//    SDK promise never hangs the runtime child.

import type { CanUseTool, PermissionResult } from "@anthropic-ai/claude-agent-sdk";
import type {
  PendingApproval,
  PermissionDecision,
  SessionEvent,
} from "@cortex-command/shared";
import { timeoutDenyMessage } from "../config.js";
import { newApprovalId } from "../ids.js";

/** The minimal session surface the broker drives (implemented by Session). */
export interface PermissionSessionSink {
  readonly key: string;
  readonly approvalTimeoutMs: number;
  logEvent(event: SessionEvent): void;
  recomputeStatus(): void;
}

type ResolveBy = "user" | "timeout";

interface PendingRecord {
  approval: PendingApproval;
  resolve: (by: ResolveBy) => void;
  timer: ReturnType<typeof setTimeout> | null;
  resolved: boolean;
}

export interface PermissionBrokerDeps {
  resolveSession: (sessionKey: string) => PermissionSessionSink | undefined;
}

export class PermissionBroker {
  private pending = new Map<string, PendingRecord>();

  constructor(private readonly deps: PermissionBrokerDeps) {}

  /** Build the canUseTool callback bound to one session. */
  makeCanUseTool(session: PermissionSessionSink): CanUseTool {
    return async (toolName, input, options): Promise<PermissionResult> => {
      const approvalId = newApprovalId();
      const now = Date.now();
      const timeoutMs = session.approvalTimeoutMs;
      const approval: PendingApproval = {
        approvalId,
        sessionKey: session.key,
        toolUseId: options.toolUseID,
        toolName,
        input,
        createdAt: now,
        expiresAt: now + timeoutMs,
        status: "pending",
      };

      const record: PendingRecord = {
        approval,
        resolve: () => {},
        timer: null,
        resolved: false,
      };
      const settled = new Promise<ResolveBy>((resolve) => {
        record.resolve = resolve;
      });
      record.timer = setTimeout(() => this.settle(approvalId, "timeout"), timeoutMs);
      this.pending.set(approvalId, record);

      // Request → EventLog (replayable) + status flip.
      session.logEvent({ type: "permission.requested", approval: { ...approval } });
      session.recomputeStatus();

      // Abort (interrupt/dispose) resolves as a default-deny.
      const onAbort = (): void => {
        this.settle(approvalId, "timeout");
      };
      if (options.signal.aborted) {
        this.settle(approvalId, "timeout");
      } else {
        options.signal.addEventListener("abort", onAbort, { once: true });
      }

      const by = await settled;
      options.signal.removeEventListener("abort", onAbort);

      const decision: PermissionDecision = approval.decision ?? "deny";
      session.logEvent({
        type: "permission.resolved",
        approvalId,
        toolUseId: approval.toolUseId,
        decision,
        resolvedBy: by,
        ...(approval.note !== undefined ? { note: approval.note } : {}),
        expired: by === "timeout",
      });
      session.recomputeStatus();

      if (decision === "approve") {
        return { behavior: "allow", updatedInput: input };
      }
      const message =
        by === "timeout"
          ? timeoutDenyMessage(timeoutMs)
          : approval.note
            ? `Denied by operator: ${approval.note}`
            : "Denied by operator.";
      return { behavior: "deny", message };
    };
  }

  /** Resolve a pending approval from an operator decision. Idempotent. */
  decide(approvalId: string, decision: PermissionDecision, note?: string): boolean {
    return this.settle(approvalId, "user", decision, note);
  }

  private settle(
    approvalId: string,
    by: ResolveBy,
    decision?: PermissionDecision,
    note?: string,
  ): boolean {
    const record = this.pending.get(approvalId);
    if (!record || record.resolved) return false;
    record.resolved = true;
    if (record.timer) clearTimeout(record.timer);

    const finalDecision: PermissionDecision =
      by === "timeout" ? "deny" : decision ?? "deny";
    record.approval.decision = finalDecision;
    record.approval.resolvedBy = by;
    record.approval.status =
      finalDecision === "approve" ? "approved" : by === "timeout" ? "expired" : "denied";
    if (note !== undefined) record.approval.note = note;

    record.resolve(by);
    return true;
  }

  /** Snapshot of still-pending approvals for a session (for the REST route). */
  pendingFor(sessionKey: string): PendingApproval[] {
    const out: PendingApproval[] = [];
    for (const record of this.pending.values()) {
      if (record.approval.sessionKey === sessionKey && record.approval.status === "pending") {
        out.push({ ...record.approval });
      }
    }
    return out;
  }

  pendingCount(sessionKey: string): number {
    let n = 0;
    for (const record of this.pending.values()) {
      if (record.approval.sessionKey === sessionKey && record.approval.status === "pending") n++;
    }
    return n;
  }

  /** Default-deny every still-pending approval for a session (on dispose). */
  cancelForSession(sessionKey: string): void {
    for (const [id, record] of this.pending) {
      if (record.approval.sessionKey === sessionKey && !record.resolved) {
        this.settle(id, "timeout");
      }
    }
  }
}
