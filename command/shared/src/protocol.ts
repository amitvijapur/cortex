// Cortex Command — WebSocket protocol contract.
//
// One WS endpoint at WS_PATH. Every frame is a JSON object with a `type`
// discriminator. This file defines both directions:
//   - ClientMessage : browser → server
//   - ServerMessage : server → browser (control frames + EventEnvelope)
//
// Session streaming events themselves live in events.ts; they reach the client
// wrapped in an EventEnvelope, which is one arm of ServerMessage. Replay is
// bracketed by replay.start / replay.end around a run of EventEnvelopes.

import type { EventEnvelope } from "./events.js";
import { isEventEnvelope } from "./events.js";
import type { Job, PermissionDecision, SessionMeta } from "./types.js";

/** WS mount path on the server. */
export const WS_PATH = "/ws";

/** Bumped on any breaking change to these message shapes. */
export const PROTOCOL_VERSION = 1;

// --------------------------------------------------------------------------- //
// Client → server
// --------------------------------------------------------------------------- //

/** One session subscription: replay from `sinceSeq`, then live. */
export interface SubChannel {
  sessionKey: string;
  /** 0 = full replay from the start of the log. */
  sinceSeq: number;
}

/** Subscribe to sessions (with replay) and optionally the jobs feed. */
export interface SubMessage {
  type: "sub";
  channels: SubChannel[];
  jobs?: boolean;
}

/** Drop subscriptions. Empty/omitted `sessionKeys` with jobs:false is a no-op. */
export interface UnsubMessage {
  type: "unsub";
  sessionKeys?: string[];
  jobs?: boolean;
}

/** Send a user turn into a session (multi-turn via the streaming input queue). */
export interface UserMessageMessage {
  type: "user.message";
  sessionKey: string;
  text: string;
  /** Optional client id echoed back on turn.user for optimistic dedupe. */
  clientMsgId?: string;
}

/** Interrupt the in-flight turn of a session. */
export interface SessionInterruptMessage {
  type: "session.interrupt";
  sessionKey: string;
}

/** Resolve a pending approval. Idempotent — the first decision wins. */
export interface PermissionDecideMessage {
  type: "permission.decide";
  approvalId: string;
  decision: PermissionDecision;
  note?: string;
}

/** Liveness ping; server replies with pong. */
export interface PingMessage {
  type: "ping";
  t?: number;
}

/** Every message the client may send. */
export type ClientMessage =
  | SubMessage
  | UnsubMessage
  | UserMessageMessage
  | SessionInterruptMessage
  | PermissionDecideMessage
  | PingMessage;

// --------------------------------------------------------------------------- //
// Server → client (control frames)
// --------------------------------------------------------------------------- //

/** First frame on connect: current sessions + jobs snapshot. */
export interface HelloMessage {
  type: "hello";
  protocolVersion: number;
  serverVersion: string;
  sessions: SessionMeta[];
  jobs: Job[];
  /** Server clock (epoch ms) so clients can align absolute expiresAt values. */
  now: number;
}

/** Opens a replay burst for a session. EventEnvelopes follow until replay.end. */
export interface ReplayStartMessage {
  type: "replay.start";
  sessionKey: string;
  fromSeq: number;
  toSeq: number;
  count: number;
  /** True when the ring buffer dropped events older than fromSeq. */
  truncated: boolean;
}

/** Closes a replay burst; live events resume after this frame. */
export interface ReplayEndMessage {
  type: "replay.end";
  sessionKey: string;
  toSeq: number;
}

/** A job was created or changed state. */
export interface JobUpdateMessage {
  type: "job.update";
  job: Job;
}

/** Liveness reply to ping. */
export interface PongMessage {
  type: "pong";
  t?: number;
}

/** Every message the server may send (EventEnvelope carries session events). */
export type ServerMessage =
  | HelloMessage
  | ReplayStartMessage
  | ReplayEndMessage
  | JobUpdateMessage
  | PongMessage
  | EventEnvelope;

// --------------------------------------------------------------------------- //
// Runtime type sets + top-level guards
// --------------------------------------------------------------------------- //

/** Every valid ClientMessage `type`. */
export const CLIENT_MESSAGE_TYPES = [
  "sub",
  "unsub",
  "user.message",
  "session.interrupt",
  "permission.decide",
  "ping",
] as const satisfies ReadonlyArray<ClientMessage["type"]>;

/** Every valid ServerMessage `type` (including the "event" envelope). */
export const SERVER_MESSAGE_TYPES = [
  "hello",
  "replay.start",
  "replay.end",
  "job.update",
  "pong",
  "event",
] as const satisfies ReadonlyArray<ServerMessage["type"]>;

const CLIENT_TYPE_SET: ReadonlySet<string> = new Set(CLIENT_MESSAGE_TYPES);
const SERVER_TYPE_SET: ReadonlySet<string> = new Set(SERVER_MESSAGE_TYPES);

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/** Narrow an unknown (e.g. a parsed WS frame) to a ClientMessage. */
export function isClientMessage(v: unknown): v is ClientMessage {
  return isRecord(v) && typeof v["type"] === "string" &&
    CLIENT_TYPE_SET.has(v["type"]);
}

/**
 * Narrow an unknown to a ServerMessage. The "event" arm is additionally
 * validated as a well-formed EventEnvelope so consumers can trust `event`.
 */
export function isServerMessage(v: unknown): v is ServerMessage {
  if (!isRecord(v) || typeof v["type"] !== "string") return false;
  if (v["type"] === "event") return isEventEnvelope(v);
  return SERVER_TYPE_SET.has(v["type"]);
}

// Re-export the envelope guard so consumers get it from the protocol surface.
export { isEventEnvelope } from "./events.js";
