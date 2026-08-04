// Cortex Command — shared domain types.
//
// These are the persistent/domain models exchanged over the wire and stored on
// disk (jobs.jsonl, event log). They are transport-agnostic: the WS envelope
// and message unions live in protocol.ts, the streaming session events live in
// events.ts, and both build on the vocabulary defined here.
//
// This file is the contract server/ and web/ compile against. Keep it
// exhaustive and additive — never repurpose a field's meaning.

// --------------------------------------------------------------------------- //
// Primitives
// --------------------------------------------------------------------------- //

/** Effort tier as declared in a Cortex routing line. */
export type Tier = "L1" | "L2" | "L3" | "L4";

/** Which permission posture a session runs under. */
export type SessionKind = "chat" | "run";

/** Named permission profile applied to a session (see profiles.ts on server). */
export type PermissionProfileName = "chat" | "run";

/**
 * Session lifecycle. Drives the SessionHeader status pill.
 * - starting  : query() created, SDK init not yet received.
 * - running   : a turn is in flight (model/tools active).
 * - idle      : init complete, no turn in flight, ready for input.
 * - awaiting_permission : blocked on one or more PendingApprovals.
 * - completed : run-style session finished its single goal (jobs).
 * - error     : unrecoverable session-level failure.
 * - disposed  : child process reaped; EventLog may still be replayable.
 */
export type SessionStatus =
  | "starting"
  | "running"
  | "idle"
  | "awaiting_permission"
  | "completed"
  | "error"
  | "disposed";

/** A resolvable permission decision. Idempotent — first decision wins. */
export type PermissionDecision = "approve" | "deny";

/** Terminal states of a PendingApproval. */
export type ApprovalStatus = "pending" | "approved" | "denied" | "expired";

/** Token usage surfaced to the UI (subset of the SDK's NonNullableUsage). */
export interface TokenUsage {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
}

// --------------------------------------------------------------------------- //
// Permissions
// --------------------------------------------------------------------------- //

/**
 * A permission profile. `allowedTools` auto-approve without a card; everything
 * else routes through canUseTool → PendingApproval. `denyPatterns` are the
 * hard denylist enforced by a PreToolUse hook (run profile), never surfaced as
 * an approvable card.
 */
export interface PermissionProfile {
  name: PermissionProfileName;
  /** Tools (optionally rule-scoped, e.g. "Edit(//proj/**)") that auto-approve. */
  allowedTools: string[];
  /** Human-readable denylist descriptions enforced via PreToolUse deny. */
  denyPatterns: string[];
  /** Absolute ms before an unresolved approval default-denies. */
  approvalTimeoutMs: number;
}

/**
 * A tool invocation blocked on a human decision. Lives in the replayable event
 * log AND on GET /api/sessions/:key, so refresh / a second tab reconstruct it.
 * `expiresAt` is absolute so countdowns survive reconnects.
 */
export interface PendingApproval {
  approvalId: string;
  sessionKey: string;
  /** SDK tool_use id this approval gates (pairs with tool.start/result). */
  toolUseId: string;
  toolName: string;
  /** Raw tool input, for rendering the request (e.g. the Bash command). */
  input: unknown;
  createdAt: number;
  expiresAt: number;
  status: ApprovalStatus;
  /** Set once resolved. */
  decision?: PermissionDecision;
  note?: string;
  /** How it resolved: a human click or the timeout default-deny. */
  resolvedBy?: "user" | "timeout";
}

// --------------------------------------------------------------------------- //
// Sessions
// --------------------------------------------------------------------------- //

/**
 * Everything the client needs to list/route a session without replaying its
 * log. Keyed by sessionKey (`sess_<ulid>`); sdkSessionId is the SDK's own
 * session_id, captured eagerly at init for resume.
 */
export interface SessionMeta {
  sessionKey: string;
  sdkSessionId: string | null;
  kind: SessionKind;
  profile: PermissionProfileName;
  cwd: string;
  title: string | null;
  status: SessionStatus;
  model: string | null;
  createdAt: number;
  updatedAt: number;
  /** Highest event seq emitted so far (client replay bookkeeping). */
  lastSeq: number;
  /** Cumulative cost across all turns in this session. */
  costUsd: number;
  /** Set when this session backs a run-queue Job. */
  jobId: string | null;
}

// --------------------------------------------------------------------------- //
// Run queue
// --------------------------------------------------------------------------- //

/** Prompt-template preset a run was launched from. Server treats all alike. */
export type JobKind = "autopilot" | "ralph" | "gsd-phase" | "custom";

/**
 * Job lifecycle. `interrupted` is a server-crash artifact (was running at
 * shutdown) and is one-click resumable via the captured sdkSessionId.
 */
export type JobState =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "interrupted"
  | "canceled";

/** Completion summary distilled from the session's ResultMessage. */
export interface JobResult {
  costUsd?: number;
  turns?: number;
  durationMs?: number;
  /** ResultMessage.result text (final assistant summary). */
  summary?: string;
  /** SDK result subtype (success / error_*). */
  subtype?: string;
  /** Populated on failure. */
  error?: string;
}

/** A queued/executing autonomous run. Metadata over an ordinary Session. */
export interface Job {
  jobId: string;
  kind: JobKind;
  prompt: string;
  cwd: string;
  state: JobState;
  title: string | null;
  /** The backing session, once started. */
  sessionKey: string | null;
  /** Captured eagerly so a crash can resume this exact SDK session. */
  sdkSessionId: string | null;
  createdAt: number;
  updatedAt: number;
  startedAt: number | null;
  finishedAt: number | null;
  result: JobResult | null;
}

// --------------------------------------------------------------------------- //
// Routing lines (Cortex chip grammar)
// --------------------------------------------------------------------------- //

/**
 * A parsed Cortex routing line, e.g.
 *   "OMC > /team > [A ∥ B] → C @ L3  [breadth=api+ui]"
 * Ported from ROUTE_RE in bin/cortex; the agent segment is further split on
 * the chip grammar (∥ parallel legs, → reconciler) for RoutingCard rendering.
 */
export interface RoutingLine {
  /** The exact matched source line (suppressed from the text block). */
  raw: string;
  system: string;
  pattern: string;
  /** Raw agent segment (null when the line has no `> Agent`). */
  agent: string | null;
  /** Parallel legs split on "∥" (empty when single/no agent). */
  parallel: string[];
  /** Reconciler after "→", if present. */
  reconciler: string | null;
  tier: Tier;
  /** Contents of the trailing "[...]" tag block, verbatim (null when absent). */
  tags: string | null;
}
