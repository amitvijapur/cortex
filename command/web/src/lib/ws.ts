// Cortex Command — reconnecting WebSocket client.
//
// Owns the single /ws socket: capped-backoff reconnect, heartbeat ping/pong
// with stale detection, and (re)subscription. On open it subscribes to every
// session already in the store at its current lastSeq — so a reconnect replays
// only the gap — and re-subscribes to any new sessions the hello announces.
// Outbound frames are queued while the socket is down and flushed on open.

import {
  WS_PATH,
  isServerMessage,
  type ClientMessage,
  type PermissionDecision,
  type ServerMessage,
  type SubChannel,
} from "@cortex-command/shared";
import {
  applyEnvelope,
  applyHello,
  applyJobUpdate,
  applyReplayEnd,
  applyReplayStart,
  readState,
  setConnection,
} from "./store";

/** The command surface the UI drives, satisfied by both WS and demo clients. */
export interface Client {
  sendUserMessage(sessionKey: string, text: string, clientMsgId?: string): void;
  sendInterrupt(sessionKey: string): void;
  sendPermissionDecision(approvalId: string, decision: PermissionDecision, note?: string): void;
  /** Subscribe to a session's stream at a given seq (idempotent). */
  subscribeSession(sessionKey: string, sinceSeq: number): void;
}

const PING_INTERVAL_MS = 20_000;
const STALE_AFTER_MS = 45_000; // no pong within this window → amber "stale"
const BACKOFF_BASE_MS = 500;
const BACKOFF_CAP_MS = 15_000;

export class WsClient implements Client {
  private ws: WebSocket | null = null;
  private backoff = BACKOFF_BASE_MS;
  private outbox: ClientMessage[] = [];
  private subscribed = new Set<string>();
  private pingTimer: number | null = null;
  private staleTimer: number | null = null;
  private lastPong = 0;
  private closed = false;

  constructor(private url: string = defaultWsUrl()) {}

  connect(): void {
    this.closed = false;
    this.open();
  }

  dispose(): void {
    this.closed = true;
    this.clearTimers();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
  }

  private open(): void {
    setConnection("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.backoff = BACKOFF_BASE_MS;
      this.lastPong = Date.now();
      setConnection("open");
      // Re-subscribe to everything we already know, from where we left off.
      const state = readState();
      const channels: SubChannel[] = Object.keys(state.sessions).map((key) => ({
        sessionKey: key,
        sinceSeq: state.sessions[key]!.lastSeq,
      }));
      this.subscribed = new Set(channels.map((c) => c.sessionKey));
      this.rawSend({ type: "sub", channels, jobs: true });
      this.flushOutbox();
      this.startHeartbeat();
    };

    ws.onmessage = (ev) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(typeof ev.data === "string" ? ev.data : "");
      } catch {
        return;
      }
      if (!isServerMessage(parsed)) return;
      this.handle(parsed);
    };

    ws.onerror = () => {
      // onclose will follow; nothing else to do.
    };

    ws.onclose = () => {
      this.clearTimers();
      this.ws = null;
      if (!this.closed) {
        setConnection("down");
        this.scheduleReconnect();
      }
    };
  }

  private handle(msg: ServerMessage): void {
    switch (msg.type) {
      case "hello": {
        applyHello(msg);
        // Subscribe to any session the server knows that we hadn't yet.
        const state = readState();
        const fresh: SubChannel[] = [];
        for (const meta of msg.sessions) {
          if (!this.subscribed.has(meta.sessionKey)) {
            const existing = state.sessions[meta.sessionKey];
            fresh.push({ sessionKey: meta.sessionKey, sinceSeq: existing ? existing.lastSeq : 0 });
            this.subscribed.add(meta.sessionKey);
          }
        }
        if (fresh.length > 0) this.rawSend({ type: "sub", channels: fresh, jobs: true });
        break;
      }
      case "replay.start":
        applyReplayStart(msg);
        break;
      case "replay.end":
        applyReplayEnd(msg);
        break;
      case "job.update":
        applyJobUpdate(msg.job);
        break;
      case "pong":
        this.lastPong = Date.now();
        if (readState().connection === "stale") setConnection("open");
        break;
      case "event":
        applyEnvelope(msg);
        break;
    }
  }

  // ---- outbound ---- //

  private rawSend(msg: ClientMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.outbox.push(msg);
    }
  }

  private flushOutbox(): void {
    const pending = this.outbox;
    this.outbox = [];
    for (const m of pending) this.rawSend(m);
  }

  subscribeSession(sessionKey: string, sinceSeq: number): void {
    this.subscribed.add(sessionKey);
    this.rawSend({ type: "sub", channels: [{ sessionKey, sinceSeq }], jobs: true });
  }

  sendUserMessage(sessionKey: string, text: string, clientMsgId?: string): void {
    this.rawSend({ type: "user.message", sessionKey, text, clientMsgId });
  }

  sendInterrupt(sessionKey: string): void {
    this.rawSend({ type: "session.interrupt", sessionKey });
  }

  sendPermissionDecision(approvalId: string, decision: PermissionDecision, note?: string): void {
    this.rawSend({ type: "permission.decide", approvalId, decision, note });
  }

  // ---- heartbeat + reconnect ---- //

  private startHeartbeat(): void {
    this.clearTimers();
    this.pingTimer = window.setInterval(() => {
      this.rawSend({ type: "ping", t: Date.now() });
    }, PING_INTERVAL_MS);
    this.staleTimer = window.setInterval(() => {
      if (Date.now() - this.lastPong > STALE_AFTER_MS) {
        if (readState().connection === "open") setConnection("stale");
      }
    }, 5_000);
  }

  private clearTimers(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.staleTimer !== null) {
      clearInterval(this.staleTimer);
      this.staleTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.closed) return;
    const jitter = Math.random() * 250;
    const delay = Math.min(this.backoff, BACKOFF_CAP_MS) + jitter;
    this.backoff = Math.min(this.backoff * 2, BACKOFF_CAP_MS);
    window.setTimeout(() => {
      if (!this.closed) this.open();
    }, delay);
  }
}

export function defaultWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return proto + "//" + window.location.host + WS_PATH;
}
