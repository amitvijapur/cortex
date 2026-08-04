// Cortex Command — session event contract.
//
// A SessionEvent is one entry in a session's append-only EventLog. The server
// translates raw SDK messages (translate.ts) into these normalized, UI-shaped
// events; the client folds them into transcript state with a pure reducer keyed
// by seq. Events are wrapped in an EventEnvelope for transport and replay.
//
// Every event carries a literal `type` discriminator. Content-bearing events
// (text/thinking/tool) optionally carry `parentToolUseId`: when non-null the
// block belongs to a subagent and the client indents it under the Task card.

import type {
  PendingApproval,
  PermissionDecision,
  RoutingLine,
  SessionStatus,
  TokenUsage,
} from "./types.js";

// --------------------------------------------------------------------------- //
// Result subtype (mirrors SDKResultMessage.subtype union)
// --------------------------------------------------------------------------- //

export type TurnResultSubtype =
  | "success"
  | "error_during_execution"
  | "error_max_turns"
  | "error_max_budget_usd"
  | "error_max_structured_output_retries";

// --------------------------------------------------------------------------- //
// Session-level events
// --------------------------------------------------------------------------- //

/** Status machine transition. */
export interface SessionStatusEvent {
  type: "session.status";
  status: SessionStatus;
  detail?: string;
}

/** A user turn was accepted (echoed so the transcript is self-contained). */
export interface TurnUserEvent {
  type: "turn.user";
  text: string;
  /** Optional client-supplied id (dedupe optimistic echoes). */
  clientMsgId?: string;
}

/** Unrecoverable session-level error (distinct from a failed turn result). */
export interface SessionErrorEvent {
  type: "session.error";
  message: string;
  code?: string;
  fatal?: boolean;
}

// --------------------------------------------------------------------------- //
// Streaming text / thinking
// --------------------------------------------------------------------------- //

/** A coalesced chunk of assistant text (append to block `index`). */
export interface TextDeltaEvent {
  type: "text.delta";
  text: string;
  /** Content-block index within the turn (keys multiple text blocks). */
  index: number;
  parentToolUseId?: string | null;
}

/** Authoritative full text for block `index` — heals any lost deltas. */
export interface TextDoneEvent {
  type: "text.done";
  text: string;
  index: number;
  parentToolUseId?: string | null;
}

/** A coalesced chunk of thinking text (append to block `index`). */
export interface ThinkingDeltaEvent {
  type: "thinking.delta";
  text: string;
  index: number;
  parentToolUseId?: string | null;
}

/** Authoritative full thinking text for block `index`. */
export interface ThinkingDoneEvent {
  type: "thinking.done";
  text: string;
  index: number;
  parentToolUseId?: string | null;
}

// --------------------------------------------------------------------------- //
// Tool calls (start → input → result, paired by toolUseId)
// --------------------------------------------------------------------------- //

/** A tool_use block began — render a spinner card immediately. */
export interface ToolStartEvent {
  type: "tool.start";
  toolUseId: string;
  name: string;
  index?: number;
  parentToolUseId?: string | null;
}

/** Full, validated tool input (arrives with the complete AssistantMessage). */
export interface ToolInputEvent {
  type: "tool.input";
  toolUseId: string;
  name: string;
  input: unknown;
  index?: number;
  parentToolUseId?: string | null;
}

/**
 * Tool result, paired to its start by toolUseId. `preview` is truncated at the
 * pipeline (first 4k + last 2k chars); when `truncated`, the full output was
 * spilled to a blob and is fetchable at `outputRef`. `structuredPatch` is
 * preferred for diff rendering when the tool provides it.
 */
export interface ToolResultEvent {
  type: "tool.result";
  toolUseId: string;
  name?: string;
  isError: boolean;
  preview: string;
  truncated: boolean;
  /** Total length of the untruncated output, when known. */
  fullLength?: number;
  /** REST path to the full output blob (set when truncated). */
  outputRef?: string;
  /** Edit/Write structured patch hunks, when the SDK supplies them. */
  structuredPatch?: unknown;
  parentToolUseId?: string | null;
}

// --------------------------------------------------------------------------- //
// Permissions (mirror of the broker's PendingApproval lifecycle)
// --------------------------------------------------------------------------- //

/** A tool is blocked awaiting a decision. Carries the full PendingApproval. */
export interface PermissionRequestedEvent {
  type: "permission.requested";
  approval: PendingApproval;
}

/** A pending approval was resolved (by a human click or the timeout). */
export interface PermissionResolvedEvent {
  type: "permission.resolved";
  approvalId: string;
  toolUseId: string;
  decision: PermissionDecision;
  resolvedBy: "user" | "timeout";
  note?: string;
  /** True when resolution was the default-deny timeout. */
  expired?: boolean;
}

// --------------------------------------------------------------------------- //
// Subagent fan-out (SubagentStart/Stop hooks + parent_tool_use_id)
// --------------------------------------------------------------------------- //

/** A subagent began under the Task tool call `parentToolUseId`. */
export interface AgentStartEvent {
  type: "agent.start";
  agentId: string;
  /** The Task tool_use id that spawned it (indent anchor). */
  parentToolUseId: string | null;
  agentType?: string;
  description?: string;
}

/** A subagent finished. */
export interface AgentStopEvent {
  type: "agent.stop";
  agentId: string;
  parentToolUseId: string | null;
  status?: "completed" | "error";
  summary?: string;
}

// --------------------------------------------------------------------------- //
// Cortex routing card
// --------------------------------------------------------------------------- //

/** A Cortex routing line was detected in completed assistant text. */
export interface RoutingCardEvent {
  type: "routing.card";
  routing: RoutingLine;
}

// --------------------------------------------------------------------------- //
// Turn result (from ResultMessage)
// --------------------------------------------------------------------------- //

/** A turn (or a run's single goal) completed — cost/usage/duration. */
export interface TurnResultEvent {
  type: "turn.result";
  subtype: TurnResultSubtype;
  isError: boolean;
  costUsd: number;
  durationMs: number;
  numTurns: number;
  /** ResultMessage.result text (final summary), when present. */
  resultText?: string;
  usage?: TokenUsage;
  /** Error strings on a failed result. */
  errors?: string[];
}

// --------------------------------------------------------------------------- //
// Union + envelope
// --------------------------------------------------------------------------- //

/** The full discriminated union of session events (discriminated on `type`). */
export type SessionEvent =
  | SessionStatusEvent
  | TurnUserEvent
  | SessionErrorEvent
  | TextDeltaEvent
  | TextDoneEvent
  | ThinkingDeltaEvent
  | ThinkingDoneEvent
  | ToolStartEvent
  | ToolInputEvent
  | ToolResultEvent
  | PermissionRequestedEvent
  | PermissionResolvedEvent
  | AgentStartEvent
  | AgentStopEvent
  | RoutingCardEvent
  | TurnResultEvent;

/** Every valid SessionEvent `type`, as a runtime source of truth. */
export const SESSION_EVENT_TYPES = [
  "session.status",
  "turn.user",
  "session.error",
  "text.delta",
  "text.done",
  "thinking.delta",
  "thinking.done",
  "tool.start",
  "tool.input",
  "tool.result",
  "permission.requested",
  "permission.resolved",
  "agent.start",
  "agent.stop",
  "routing.card",
  "turn.result",
] as const satisfies ReadonlyArray<SessionEvent["type"]>;

const SESSION_EVENT_TYPE_SET: ReadonlySet<string> = new Set(SESSION_EVENT_TYPES);

/**
 * One logged event, addressed to a session and ordered by `seq`. This is the
 * transport unit the server broadcasts and replays; `seq` is monotonic per
 * session and drives idempotent client folding.
 */
export interface EventEnvelope {
  type: "event";
  sessionKey: string;
  seq: number;
  /** Epoch ms the event was logged. */
  ts: number;
  event: SessionEvent;
}

// --------------------------------------------------------------------------- //
// Guards
// --------------------------------------------------------------------------- //

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/** Narrow an unknown value to a SessionEvent by its `type` discriminator. */
export function isSessionEvent(v: unknown): v is SessionEvent {
  return isRecord(v) && typeof v["type"] === "string" &&
    SESSION_EVENT_TYPE_SET.has(v["type"]);
}

/** Narrow an unknown value to an EventEnvelope. */
export function isEventEnvelope(v: unknown): v is EventEnvelope {
  return isRecord(v) && v["type"] === "event" &&
    typeof v["sessionKey"] === "string" &&
    typeof v["seq"] === "number" &&
    isSessionEvent(v["event"]);
}
