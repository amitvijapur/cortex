// Cortex Command — SessionManager: the session registry.
//
// Owns the `Map<sessionKey, Session>` and the shared PermissionBroker (the
// broker resolves a session by key to raise approval cards into its log).
// Enforces maxChatSessions=1 on create (returns the existing key as a conflict
// so the route can 409). Disposed sessions are retained in the map so their
// EventLog stays replayable for transcript click-through.

import type { EventEnvelope, SessionKind, SessionMeta } from "@cortex-command/shared";
import type { PermissionProfileName } from "@cortex-command/shared";
import { MAX_CHAT_SESSIONS } from "../config.js";
import { newSessionKey } from "../ids.js";
import { PermissionBroker } from "../permissions/PermissionBroker.js";
import { resolveProfile } from "../permissions/profiles.js";
import { Session, type QueryFactory } from "./Session.js";

export interface CreateSessionInput {
  cwd: string;
  title?: string | null;
  resumeSdkSessionId?: string | null;
  profile?: PermissionProfileName;
  mcp?: boolean;
  kind?: SessionKind;
  jobId?: string | null;
  /** Test-only per-session overrides (never set from the network). */
  queryFactory?: QueryFactory;
  approvalTimeoutMs?: number;
}

export type CreateSessionResult =
  | { ok: true; sessionKey: string }
  | { ok: false; conflict: string };

export interface SessionManagerDeps {
  broadcast: (env: EventEnvelope) => void;
  /** Default factory injected for the whole server (real SDK, or a test fake). */
  defaultQueryFactory?: QueryFactory;
}

export class SessionManager {
  readonly broker: PermissionBroker;
  private readonly sessions = new Map<string, Session>();

  constructor(private readonly deps: SessionManagerDeps) {
    this.broker = new PermissionBroker({
      resolveSession: (key) => this.sessions.get(key),
    });
  }

  create(input: CreateSessionInput): CreateSessionResult {
    const kind: SessionKind = input.kind ?? "chat";

    if (kind === "chat") {
      const live = this.liveChatSessions();
      if (live.length >= MAX_CHAT_SESSIONS) {
        const existing = live[0];
        if (existing) return { ok: false, conflict: existing.key };
      }
    }

    const key = newSessionKey();
    const profileName: PermissionProfileName = input.profile ?? (kind === "run" ? "run" : "chat");
    const profile = resolveProfile(profileName, input.cwd);

    const session = new Session({
      key,
      cwd: input.cwd,
      kind,
      profile,
      broker: this.broker,
      broadcast: this.deps.broadcast,
      queryFactory: input.queryFactory ?? this.deps.defaultQueryFactory,
      title: input.title ?? null,
      resumeSdkSessionId: input.resumeSdkSessionId ?? null,
      mcp: input.mcp ?? true,
      jobId: input.jobId ?? null,
      ...(input.approvalTimeoutMs !== undefined
        ? { approvalTimeoutMs: input.approvalTimeoutMs }
        : {}),
    });

    this.sessions.set(key, session);
    session.start();
    return { ok: true, sessionKey: key };
  }

  get(key: string): Session | undefined {
    return this.sessions.get(key);
  }

  list(): SessionMeta[] {
    return [...this.sessions.values()].map((s) => s.meta);
  }

  private liveChatSessions(): Session[] {
    return [...this.sessions.values()].filter(
      (s) => s.kind === "chat" && s.statusValue !== "disposed",
    );
  }

  async dispose(key: string): Promise<boolean> {
    const session = this.sessions.get(key);
    if (!session) return false;
    await session.dispose(); // retained in the map for replay
    return true;
  }

  async disposeAll(): Promise<void> {
    await Promise.all([...this.sessions.values()].map((s) => s.dispose()));
  }
}
