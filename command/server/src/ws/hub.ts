// Cortex Command — WebSocket hub (single /ws endpoint).
//
// One WS mount. On connect a client receives `hello` (session + job snapshot +
// server clock). It then `sub`scribes to sessions with a `sinceSeq`; the hub
// replays that session's EventLog bracketed by replay.start / replay.end, then
// streams live events. Broadcast is per-subscription by sessionKey. Per-client
// backpressure: when a socket's bufferedAmount exceeds the cap, delta frames are
// skipped for that client (the authoritative text.done heals the gap).

import type { Server as HttpServer } from "node:http";
import { WebSocket, WebSocketServer } from "ws";
import type {
  ClientMessage,
  EventEnvelope,
  HelloMessage,
  Job,
  ServerMessage,
} from "@cortex-command/shared";
import { isClientMessage, PROTOCOL_VERSION, WS_PATH } from "@cortex-command/shared";
import { SERVER_VERSION, WS_HEARTBEAT_MS, WS_MAX_BUFFERED_BYTES } from "../config.js";
import type { PermissionBroker } from "../permissions/PermissionBroker.js";
import type { SessionManager } from "../session/SessionManager.js";

interface ClientState {
  subs: Set<string>;
  jobs: boolean;
  isAlive: boolean;
}

export interface WsHubDeps {
  server: HttpServer;
  manager: SessionManager;
  broker: PermissionBroker;
  /** Jobs feed is M2; supply a snapshot getter when RunQueue lands. */
  getJobs?: () => Job[];
}

const DELTA_TYPES = new Set(["text.delta", "thinking.delta"]);

export class WsHub {
  private readonly wss: WebSocketServer;
  private readonly clients = new Map<WebSocket, ClientState>();
  private readonly heartbeat: ReturnType<typeof setInterval>;

  constructor(private readonly deps: WsHubDeps) {
    this.wss = new WebSocketServer({ server: deps.server, path: WS_PATH });
    this.wss.on("connection", (ws) => this.onConnection(ws));
    this.heartbeat = setInterval(() => this.pingAll(), WS_HEARTBEAT_MS);
    this.heartbeat.unref?.();
  }

  // ----------------------------------------------------------------------- //
  // Connection lifecycle
  // ----------------------------------------------------------------------- //

  private onConnection(ws: WebSocket): void {
    this.clients.set(ws, { subs: new Set(), jobs: false, isAlive: true });
    ws.on("pong", () => {
      const state = this.clients.get(ws);
      if (state) state.isAlive = true;
    });
    ws.on("message", (data) => this.onMessage(ws, data.toString()));
    ws.on("close", () => this.clients.delete(ws));
    ws.on("error", () => this.clients.delete(ws));
    this.send(ws, this.helloFrame());
  }

  private helloFrame(): HelloMessage {
    return {
      type: "hello",
      protocolVersion: PROTOCOL_VERSION,
      serverVersion: SERVER_VERSION,
      sessions: this.deps.manager.list(),
      jobs: this.deps.getJobs ? this.deps.getJobs() : [],
      now: Date.now(),
    };
  }

  private onMessage(ws: WebSocket, raw: string): void {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    if (!isClientMessage(parsed)) return;
    const msg = parsed as ClientMessage;
    const state = this.clients.get(ws);
    if (!state) return;

    switch (msg.type) {
      case "sub":
        for (const channel of msg.channels) {
          state.subs.add(channel.sessionKey);
          this.replay(ws, channel.sessionKey, channel.sinceSeq);
        }
        if (msg.jobs) state.jobs = true;
        break;
      case "unsub":
        for (const key of msg.sessionKeys ?? []) state.subs.delete(key);
        if (msg.jobs) state.jobs = false;
        break;
      case "user.message":
        this.deps.manager.get(msg.sessionKey)?.pushUserMessage(msg.text, msg.clientMsgId);
        break;
      case "session.interrupt":
        void this.deps.manager.get(msg.sessionKey)?.interrupt();
        break;
      case "permission.decide":
        this.deps.broker.decide(msg.approvalId, msg.decision, msg.note);
        break;
      case "ping":
        this.send(ws, { type: "pong", ...(msg.t !== undefined ? { t: msg.t } : {}) });
        break;
    }
  }

  private replay(ws: WebSocket, sessionKey: string, sinceSeq: number): void {
    const session = this.deps.manager.get(sessionKey);
    if (!session) return;
    const slice = session.eventLog.replay(sinceSeq);
    this.send(ws, {
      type: "replay.start",
      sessionKey,
      fromSeq: slice.fromSeq,
      toSeq: slice.toSeq,
      count: slice.count,
      truncated: slice.truncated,
    });
    for (const env of slice.events) this.send(ws, env);
    this.send(ws, { type: "replay.end", sessionKey, toSeq: slice.toSeq });
  }

  // ----------------------------------------------------------------------- //
  // Broadcast
  // ----------------------------------------------------------------------- //

  broadcastEvent(env: EventEnvelope): void {
    const isDelta = DELTA_TYPES.has(env.event.type);
    for (const [ws, state] of this.clients) {
      if (!state.subs.has(env.sessionKey)) continue;
      if (ws.readyState !== WebSocket.OPEN) continue;
      // Per-client backpressure: drop deltas for a slow socket (done heals).
      if (isDelta && ws.bufferedAmount > WS_MAX_BUFFERED_BYTES) continue;
      this.send(ws, env);
    }
  }

  broadcastJob(job: Job): void {
    for (const [ws, state] of this.clients) {
      if (!state.jobs) continue;
      if (ws.readyState !== WebSocket.OPEN) continue;
      this.send(ws, { type: "job.update", job });
    }
  }

  // ----------------------------------------------------------------------- //
  // Plumbing
  // ----------------------------------------------------------------------- //

  private send(ws: WebSocket, msg: ServerMessage): void {
    if (ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(msg));
  }

  private pingAll(): void {
    for (const [ws, state] of this.clients) {
      if (!state.isAlive) {
        ws.terminate();
        this.clients.delete(ws);
        continue;
      }
      state.isAlive = false;
      try {
        ws.ping();
      } catch {
        /* ignore */
      }
    }
  }

  close(): Promise<void> {
    clearInterval(this.heartbeat);
    for (const ws of this.clients.keys()) {
      try {
        ws.terminate();
      } catch {
        /* ignore */
      }
    }
    this.clients.clear();
    return new Promise((resolve) => this.wss.close(() => resolve()));
  }
}
