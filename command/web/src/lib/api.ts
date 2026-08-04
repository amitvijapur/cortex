// Cortex Command — REST client.
//
// Thin typed wrappers over the server's /api surface. Same-origin in
// production (Express serves web/dist); in dev, Vite proxies /api → :7788.
// Every call returns parsed JSON or throws an ApiError with the status.

import type { Job, PendingApproval, SessionMeta } from "@cortex-command/shared";

export class ApiError extends Error {
  status: number;
  /** Parsed response body, when the server returned JSON (e.g. 409 conflict). */
  body?: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await res.text();
  const body = text ? safeJson(text) : undefined;
  if (!res.ok) {
    const msg =
      (body && typeof body === "object" && "error" in body
        ? String((body as Record<string, unknown>)["error"])
        : res.statusText) || "request failed";
    throw new ApiError(res.status, msg, body);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// ---- shapes the REST endpoints return ----------------------------------- //

export interface HealthResponse {
  ok: boolean;
  serverVersion?: string;
  now?: number;
}

/** One entry from GET /api/projects/suggest. */
export interface ProjectSuggestion {
  path: string;
  label?: string;
  /** Optional recency/relevance hint from the server. */
  lastUsed?: number;
}

/** One entry from GET /api/history (SDK listSessions). */
export interface HistoryEntry {
  sdkSessionId: string;
  cwd: string;
  title?: string | null;
  updatedAt?: number;
  messageCount?: number;
}

export interface CreateSessionBody {
  cwd: string;
  kind?: "chat" | "run";
  title?: string | null;
  /** Resume a prior SDK session instead of starting fresh. */
  resumeSdkSessionId?: string;
}

/**
 * GET /api/sessions/:key — the per-session detail route. Carries pendingApprovals
 * as belt-and-braces beyond replay, so an attach/reconnect can sanity-check the
 * store's derived pending set (replay remains the primary source of truth).
 */
export interface SessionDetail {
  meta: SessionMeta;
  pendingApprovals: PendingApproval[];
  lastSeq: number;
}

// ---- endpoints ---------------------------------------------------------- //

export const api = {
  health(): Promise<HealthResponse> {
    return req<HealthResponse>("/api/health");
  },

  suggestProjects(q: string): Promise<ProjectSuggestion[]> {
    const qs = q ? "?q=" + encodeURIComponent(q) : "";
    return req<ProjectSuggestion[]>("/api/projects/suggest" + qs);
  },

  listSessions(): Promise<SessionMeta[]> {
    return req<SessionMeta[]>("/api/sessions");
  },

  getSession(key: string): Promise<SessionDetail> {
    return req<SessionDetail>("/api/sessions/" + encodeURIComponent(key));
  },

  createSession(body: CreateSessionBody): Promise<SessionMeta> {
    return req<SessionMeta>("/api/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  interruptSession(key: string): Promise<{ ok: boolean }> {
    return req<{ ok: boolean }>(
      "/api/sessions/" + encodeURIComponent(key) + "/interrupt",
      { method: "POST" },
    );
  },

  history(): Promise<HistoryEntry[]> {
    return req<HistoryEntry[]>("/api/history");
  },

  historyMessages(sdkSessionId: string): Promise<unknown[]> {
    return req<unknown[]>(
      "/api/history/" + encodeURIComponent(sdkSessionId) + "/messages",
    );
  },

  /** Absolute REST path to a spilled tool-output blob (for "view full output"). */
  toolOutputUrl(sessionKey: string, toolUseId: string): string {
    return (
      "/api/sessions/" +
      encodeURIComponent(sessionKey) +
      "/tool-output/" +
      encodeURIComponent(toolUseId)
    );
  },

  listJobs(): Promise<Job[]> {
    return req<Job[]>("/api/jobs");
  },
};
