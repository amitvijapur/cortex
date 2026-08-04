// Cortex Command — hand-rolled reactive store (useSyncExternalStore).
//
// Single source of truth for the UI. The transcript is a DETERMINISTIC FOLD
// over the session's event log: applyEvent() is a pure reducer keyed by seq,
// idempotent (drops seq <= lastSeq), so a replay from 0 reproduces byte-for-byte
// the same block list, pending permission cards, spinners, and cost totals as
// the live stream did. Refresh / second tab / reconnect all reconcile by
// re-subscribing at sinceSeq and re-folding.

import { useSyncExternalStore } from "react";
import type {
  EventEnvelope,
  HelloMessage,
  Job,
  PendingApproval,
  ReplayEndMessage,
  ReplayStartMessage,
  RoutingLine,
  SessionEvent,
  SessionMeta,
  SessionStatus,
  TokenUsage,
  TurnResultSubtype,
} from "@cortex-command/shared";

// --------------------------------------------------------------------------- //
// Block model — the folded transcript
// --------------------------------------------------------------------------- //

export interface ToolResultData {
  isError: boolean;
  preview: string;
  truncated: boolean;
  fullLength?: number;
  outputRef?: string;
  structuredPatch?: unknown;
}

export type Block =
  | { kind: "user"; id: string; seq: number; parentToolUseId: string | null; text: string }
  | {
      kind: "text";
      id: string;
      seq: number;
      parentToolUseId: string | null;
      key: string;
      text: string;
      done: boolean;
    }
  | {
      kind: "thinking";
      id: string;
      seq: number;
      parentToolUseId: string | null;
      key: string;
      text: string;
      done: boolean;
    }
  | {
      kind: "tool";
      id: string;
      seq: number;
      parentToolUseId: string | null;
      toolUseId: string;
      name: string;
      input?: unknown;
      running: boolean;
      result?: ToolResultData;
      /** Set when a permission gate is attached to this tool call. */
      approvalId?: string;
    }
  | { kind: "routing"; id: string; seq: number; parentToolUseId: string | null; routing: RoutingLine }
  | {
      kind: "turnresult";
      id: string;
      seq: number;
      parentToolUseId: string | null;
      subtype: TurnResultSubtype;
      isError: boolean;
      costUsd: number;
      durationMs: number;
      numTurns: number;
      resultText?: string;
      usage?: TokenUsage;
    };

export interface AgentInfo {
  agentId: string;
  parentToolUseId: string | null;
  agentType?: string;
  description?: string;
  status: "running" | "completed" | "error";
  summary?: string;
}

export interface SessionState {
  meta: SessionMeta;
  status: SessionStatus;
  blocks: Block[];
  /** by approvalId */
  approvals: Record<string, PendingApproval>;
  /** by parentToolUseId (the spawning Task tool id); agentId when no parent */
  agents: Record<string, AgentInfo>;
  cost: number;
  lastSeq: number;
  /** Monotonic turn ordinal; increments on each accepted user turn. */
  curTurn: number;
  error: string | null;
}

export type ConnectionState = "connecting" | "open" | "stale" | "down";

export interface AppState {
  connection: ConnectionState;
  serverVersion: string;
  /** clientNow - serverNow at last hello; align absolute expiresAt values. */
  clockSkew: number;
  sessions: Record<string, SessionState>;
  jobs: Record<string, Job>;
}

// --------------------------------------------------------------------------- //
// Snapshot + subscription plumbing
// --------------------------------------------------------------------------- //

let snapshot: AppState = {
  connection: "connecting",
  serverVersion: "",
  clockSkew: 0,
  sessions: {},
  jobs: {},
};

const listeners = new Set<() => void>();

function emit(next: AppState): void {
  snapshot = next;
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getSnapshot(): AppState {
  return snapshot;
}

/** Subscribe to a selected slice. Selector must return a stable ref/primitive. */
export function useStore<T>(selector: (s: AppState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(snapshot),
    () => selector(snapshot),
  );
}

/** Escape hatch for imperative reads (e.g. WS resubscribe bookkeeping). */
export function readState(): AppState {
  return snapshot;
}

/** Convert a server-epoch timestamp to a client-clock timestamp. */
export function serverToClient(serverEpochMs: number): number {
  return serverEpochMs + snapshot.clockSkew;
}

// --------------------------------------------------------------------------- //
// Session bootstrap
// --------------------------------------------------------------------------- //

function blankSession(meta: SessionMeta): SessionState {
  return {
    meta,
    status: meta.status,
    blocks: [],
    approvals: {},
    agents: {},
    cost: 0,
    lastSeq: 0,
    curTurn: 0,
    error: null,
  };
}

/** Placeholder meta for events that arrive before a hello/create (robustness). */
function placeholderMeta(sessionKey: string): SessionMeta {
  const now = Date.now();
  return {
    sessionKey,
    sdkSessionId: null,
    kind: "chat",
    profile: "chat",
    cwd: "",
    title: null,
    status: "starting",
    model: null,
    createdAt: now,
    updatedAt: now,
    lastSeq: 0,
    costUsd: 0,
    jobId: null,
  };
}

// --------------------------------------------------------------------------- //
// Block helpers (immutable)
// --------------------------------------------------------------------------- //

function findLastIndex(blocks: Block[], pred: (b: Block) => boolean): number {
  for (let i = blocks.length - 1; i >= 0; i--) {
    if (pred(blocks[i]!)) return i;
  }
  return -1;
}

function replaceAt(blocks: Block[], idx: number, block: Block): Block[] {
  const next = blocks.slice();
  next[idx] = block;
  return next;
}

// --------------------------------------------------------------------------- //
// The reducer — pure fold of one SessionEvent
// --------------------------------------------------------------------------- //

function reduce(s: SessionState, ev: SessionEvent, seq: number, ts: number): SessionState {
  const parent = "parentToolUseId" in ev ? (ev.parentToolUseId ?? null) : null;

  switch (ev.type) {
    case "session.status":
      return { ...s, status: ev.status, meta: { ...s.meta, status: ev.status } };

    case "session.error":
      return {
        ...s,
        error: ev.message,
        status: ev.fatal ? "error" : s.status,
      };

    case "turn.user": {
      const block: Block = {
        kind: "user",
        id: "u" + seq,
        seq,
        parentToolUseId: parent,
        text: ev.text,
      };
      return { ...s, blocks: [...s.blocks, block], curTurn: s.curTurn + 1 };
    }

    case "text.delta":
    case "text.done": {
      const key = "t" + s.curTurn + ":" + (parent ?? "_") + ":i" + ev.index;
      const idx = findLastIndex(s.blocks, (b) => b.kind === "text" && b.key === key);
      if (ev.type === "text.done") {
        const block: Block = {
          kind: "text",
          id: idx >= 0 ? s.blocks[idx]!.id : "t" + seq,
          seq: idx >= 0 ? s.blocks[idx]!.seq : seq,
          parentToolUseId: parent,
          key,
          text: ev.text,
          done: true,
        };
        return idx >= 0
          ? { ...s, blocks: replaceAt(s.blocks, idx, block) }
          : { ...s, blocks: [...s.blocks, block] };
      }
      // delta
      if (idx >= 0) {
        const prev = s.blocks[idx]!;
        const block: Block = {
          kind: "text",
          id: prev.id,
          seq: prev.seq,
          parentToolUseId: parent,
          key,
          text: (prev.kind === "text" ? prev.text : "") + ev.text,
          done: false,
        };
        return { ...s, blocks: replaceAt(s.blocks, idx, block) };
      }
      const block: Block = {
        kind: "text",
        id: "t" + seq,
        seq,
        parentToolUseId: parent,
        key,
        text: ev.text,
        done: false,
      };
      return { ...s, blocks: [...s.blocks, block] };
    }

    case "thinking.delta":
    case "thinking.done": {
      const key = "k" + s.curTurn + ":" + (parent ?? "_") + ":i" + ev.index;
      const idx = findLastIndex(s.blocks, (b) => b.kind === "thinking" && b.key === key);
      if (ev.type === "thinking.done") {
        const block: Block = {
          kind: "thinking",
          id: idx >= 0 ? s.blocks[idx]!.id : "k" + seq,
          seq: idx >= 0 ? s.blocks[idx]!.seq : seq,
          parentToolUseId: parent,
          key,
          text: ev.text,
          done: true,
        };
        return idx >= 0
          ? { ...s, blocks: replaceAt(s.blocks, idx, block) }
          : { ...s, blocks: [...s.blocks, block] };
      }
      if (idx >= 0) {
        const prev = s.blocks[idx]!;
        const block: Block = {
          kind: "thinking",
          id: prev.id,
          seq: prev.seq,
          parentToolUseId: parent,
          key,
          text: (prev.kind === "thinking" ? prev.text : "") + ev.text,
          done: false,
        };
        return { ...s, blocks: replaceAt(s.blocks, idx, block) };
      }
      const block: Block = {
        kind: "thinking",
        id: "k" + seq,
        seq,
        parentToolUseId: parent,
        key,
        text: ev.text,
        done: false,
      };
      return { ...s, blocks: [...s.blocks, block] };
    }

    case "tool.start": {
      const idx = findLastIndex(s.blocks, (b) => b.kind === "tool" && b.toolUseId === ev.toolUseId);
      if (idx >= 0) return s; // already have it (e.g. created by permission.requested)
      const block: Block = {
        kind: "tool",
        id: "tool" + ev.toolUseId,
        seq,
        parentToolUseId: parent,
        toolUseId: ev.toolUseId,
        name: ev.name,
        running: true,
      };
      return { ...s, blocks: [...s.blocks, block] };
    }

    case "tool.input": {
      const idx = findLastIndex(s.blocks, (b) => b.kind === "tool" && b.toolUseId === ev.toolUseId);
      if (idx < 0) {
        const block: Block = {
          kind: "tool",
          id: "tool" + ev.toolUseId,
          seq,
          parentToolUseId: parent,
          toolUseId: ev.toolUseId,
          name: ev.name,
          input: ev.input,
          running: true,
        };
        return { ...s, blocks: [...s.blocks, block] };
      }
      const prev = s.blocks[idx]!;
      if (prev.kind !== "tool") return s;
      return {
        ...s,
        blocks: replaceAt(s.blocks, idx, { ...prev, name: ev.name, input: ev.input }),
      };
    }

    case "tool.result": {
      const idx = findLastIndex(s.blocks, (b) => b.kind === "tool" && b.toolUseId === ev.toolUseId);
      const result: ToolResultData = {
        isError: ev.isError,
        preview: ev.preview,
        truncated: ev.truncated,
        fullLength: ev.fullLength,
        outputRef: ev.outputRef,
        structuredPatch: ev.structuredPatch,
      };
      if (idx < 0) {
        const block: Block = {
          kind: "tool",
          id: "tool" + ev.toolUseId,
          seq,
          parentToolUseId: parent,
          toolUseId: ev.toolUseId,
          name: ev.name ?? "tool",
          running: false,
          result,
        };
        return { ...s, blocks: [...s.blocks, block] };
      }
      const prev = s.blocks[idx]!;
      if (prev.kind !== "tool") return s;
      return {
        ...s,
        blocks: replaceAt(s.blocks, idx, { ...prev, running: false, result }),
      };
    }

    case "permission.requested": {
      const ap = ev.approval;
      const approvals = { ...s.approvals, [ap.approvalId]: ap };
      // Attach to (or synthesize) the tool block this gates.
      const idx = findLastIndex(s.blocks, (b) => b.kind === "tool" && b.toolUseId === ap.toolUseId);
      if (idx < 0) {
        const block: Block = {
          kind: "tool",
          id: "tool" + ap.toolUseId,
          seq,
          parentToolUseId: parent,
          toolUseId: ap.toolUseId,
          name: ap.toolName,
          input: ap.input,
          running: false,
          approvalId: ap.approvalId,
        };
        return { ...s, approvals, blocks: [...s.blocks, block] };
      }
      const prev = s.blocks[idx]!;
      if (prev.kind !== "tool") return { ...s, approvals };
      return {
        ...s,
        approvals,
        blocks: replaceAt(s.blocks, idx, {
          ...prev,
          approvalId: ap.approvalId,
          input: prev.input ?? ap.input,
        }),
      };
    }

    case "permission.resolved": {
      const prev = s.approvals[ev.approvalId];
      if (!prev) {
        // Resolve for an approval we never saw requested — record a stub.
        const stub: PendingApproval = {
          approvalId: ev.approvalId,
          sessionKey: s.meta.sessionKey,
          toolUseId: ev.toolUseId,
          toolName: "tool",
          input: null,
          createdAt: ts,
          expiresAt: ts,
          status: ev.decision === "approve" ? "approved" : ev.expired ? "expired" : "denied",
          decision: ev.decision,
          note: ev.note,
          resolvedBy: ev.resolvedBy,
        };
        return { ...s, approvals: { ...s.approvals, [ev.approvalId]: stub } };
      }
      const updated: PendingApproval = {
        ...prev,
        status: ev.decision === "approve" ? "approved" : ev.expired ? "expired" : "denied",
        decision: ev.decision,
        note: ev.note ?? prev.note,
        resolvedBy: ev.resolvedBy,
      };
      return { ...s, approvals: { ...s.approvals, [ev.approvalId]: updated } };
    }

    case "agent.start": {
      const akey = ev.parentToolUseId ?? ev.agentId;
      const info: AgentInfo = {
        agentId: ev.agentId,
        parentToolUseId: ev.parentToolUseId,
        agentType: ev.agentType,
        description: ev.description,
        status: "running",
      };
      return { ...s, agents: { ...s.agents, [akey]: info } };
    }

    case "agent.stop": {
      const akey = ev.parentToolUseId ?? ev.agentId;
      const prev = s.agents[akey];
      const info: AgentInfo = {
        agentId: ev.agentId,
        parentToolUseId: ev.parentToolUseId,
        agentType: prev?.agentType,
        description: prev?.description,
        status: ev.status === "error" ? "error" : "completed",
        summary: ev.summary,
      };
      return { ...s, agents: { ...s.agents, [akey]: info } };
    }

    case "routing.card": {
      const block: Block = {
        kind: "routing",
        id: "r" + seq,
        seq,
        parentToolUseId: parent,
        routing: ev.routing,
      };
      return { ...s, blocks: [...s.blocks, block] };
    }

    case "turn.result": {
      const block: Block = {
        kind: "turnresult",
        id: "res" + seq,
        seq,
        parentToolUseId: parent,
        subtype: ev.subtype,
        isError: ev.isError,
        costUsd: ev.costUsd,
        durationMs: ev.durationMs,
        numTurns: ev.numTurns,
        resultText: ev.resultText,
        usage: ev.usage,
      };
      return {
        ...s,
        blocks: [...s.blocks, block],
        cost: s.cost + (Number.isFinite(ev.costUsd) ? ev.costUsd : 0),
        meta: { ...s.meta, costUsd: s.cost + (Number.isFinite(ev.costUsd) ? ev.costUsd : 0) },
      };
    }

    default:
      return s;
  }
}

// --------------------------------------------------------------------------- //
// Public mutations (called by the WS/demo client)
// --------------------------------------------------------------------------- //

/** Apply one event envelope. Idempotent by seq — drops replays of seen events. */
export function applyEnvelope(env: EventEnvelope): void {
  const existing = snapshot.sessions[env.sessionKey];
  const session = existing ?? blankSession(placeholderMeta(env.sessionKey));
  if (env.seq <= session.lastSeq) return; // already folded
  const reduced = reduce(session, env.event, env.seq, env.ts);
  const next: SessionState = { ...reduced, lastSeq: env.seq };
  emit({
    ...snapshot,
    sessions: { ...snapshot.sessions, [env.sessionKey]: next },
  });
}

/** Merge the hello snapshot: known sessions keep their fold; new ones seed at 0. */
export function applyHello(msg: HelloMessage): void {
  const sessions = { ...snapshot.sessions };
  for (const meta of msg.sessions) {
    const existing = sessions[meta.sessionKey];
    if (existing) {
      sessions[meta.sessionKey] = { ...existing, meta: { ...existing.meta, ...meta } };
    } else {
      sessions[meta.sessionKey] = blankSession(meta);
    }
  }
  const jobs: Record<string, Job> = {};
  for (const j of msg.jobs) jobs[j.jobId] = j;
  emit({
    ...snapshot,
    serverVersion: msg.serverVersion,
    clockSkew: Date.now() - msg.now,
    sessions,
    jobs: { ...snapshot.jobs, ...jobs },
  });
}

export function applyReplayStart(_msg: ReplayStartMessage): void {
  // Replay is just a burst of envelopes folded by seq — no special handling
  // needed for correctness. Hook retained for future truncation banners.
}

export function applyReplayEnd(_msg: ReplayEndMessage): void {
  // no-op; live events resume naturally after the burst.
}

export function applyJobUpdate(job: Job): void {
  emit({ ...snapshot, jobs: { ...snapshot.jobs, [job.jobId]: job } });
}

export function setConnection(state: ConnectionState): void {
  if (snapshot.connection === state) return;
  emit({ ...snapshot, connection: state });
}

/** Seed a session locally (e.g. right after createSession, before hello). */
export function seedSession(meta: SessionMeta): void {
  if (snapshot.sessions[meta.sessionKey]) return;
  emit({
    ...snapshot,
    sessions: { ...snapshot.sessions, [meta.sessionKey]: blankSession(meta) },
  });
}

// --------------------------------------------------------------------------- //
// Selectors
// --------------------------------------------------------------------------- //

export function selectSession(key: string | null) {
  return (s: AppState): SessionState | null => (key ? (s.sessions[key] ?? null) : null);
}

/** Count of still-pending approvals across all sessions. */
export function selectPendingApprovalCount(s: AppState): number {
  let n = 0;
  for (const key of Object.keys(s.sessions)) {
    const sess = s.sessions[key]!;
    for (const id of Object.keys(sess.approvals)) {
      if (sess.approvals[id]!.status === "pending") n++;
    }
  }
  return n;
}

/** Total cost across all sessions (CostTicker). */
export function selectTotalCost(s: AppState): number {
  let c = 0;
  for (const key of Object.keys(s.sessions)) c += s.sessions[key]!.cost;
  return c;
}

/** The first pending approval id (for the TopBar badge → scroll target). */
export function selectFirstPendingApprovalId(s: AppState): string | null {
  for (const key of Object.keys(s.sessions)) {
    const sess = s.sessions[key]!;
    for (const id of Object.keys(sess.approvals)) {
      if (sess.approvals[id]!.status === "pending") return id;
    }
  }
  return null;
}
