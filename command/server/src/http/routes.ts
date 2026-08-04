// Cortex Command — REST API router.
//
// Everything the SPA needs beyond the WS stream: health, project-path
// autocomplete, session CRUD + interrupt, and on-disk session history via the
// SDK's listSessions(). M2-only surfaces (history messages, tool-output blobs,
// jobs) answer 501 so the client can feature-detect without guessing.

import { statSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { listSessions } from "@anthropic-ai/claude-agent-sdk";
import { Router } from "express";
import type { PermissionProfileName } from "@cortex-command/shared";
import { SERVER_VERSION } from "../config.js";
import type { PermissionBroker } from "../permissions/PermissionBroker.js";
import type { SessionManager } from "../session/SessionManager.js";

export interface ApiRouterDeps {
  manager: SessionManager;
  broker: PermissionBroker;
}

const M2 = { error: "Not implemented (M2)" };

export function createApiRouter(deps: ApiRouterDeps): Router {
  const router = Router();
  const { manager, broker } = deps;

  router.get("/health", (_req, res) => {
    res.json({ ok: true, serverVersion: SERVER_VERSION, now: Date.now() });
  });

  // Read-only directory autocomplete (dirs only, ~ expansion). `q` is primary;
  // `path` is kept as an alias. Returns a bare array of { path } objects.
  router.get("/projects/suggest", (req, res) => {
    const input =
      typeof req.query["q"] === "string"
        ? req.query["q"]
        : typeof req.query["path"] === "string"
          ? req.query["path"]
          : "";
    void suggestDirs(input).then((dirs) => res.json(dirs.map((path) => ({ path }))));
  });

  // Create a session. Never blocks on init — returns the key immediately.
  router.post("/sessions", (req, res) => {
    const body = (req.body ?? {}) as Record<string, unknown>;
    const cwd = typeof body["cwd"] === "string" ? body["cwd"].trim() : "";
    if (!cwd) {
      res.status(400).json({ error: "cwd is required" });
      return;
    }
    let cwdStat;
    try {
      cwdStat = statSync(cwd);
    } catch {
      res.status(400).json({ error: `cwd does not exist: ${cwd}` });
      return;
    }
    if (!cwdStat.isDirectory()) {
      res.status(400).json({ error: `cwd is not a directory: ${cwd}` });
      return;
    }

    // `kind` is an alias that maps to the profile: run → run profile + kind,
    // else chat. An explicit `profile` still wins.
    const kind: "chat" | "run" = body["kind"] === "run" ? "run" : "chat";
    const profile = parseProfile(body["profile"]) ?? (kind === "run" ? "run" : "chat");
    const result = manager.create({
      cwd,
      kind,
      profile,
      title: typeof body["title"] === "string" ? body["title"] : null,
      resumeSdkSessionId:
        typeof body["resumeSdkSessionId"] === "string" ? body["resumeSdkSessionId"] : null,
      mcp: body["mcp"] === false ? false : true,
    });

    if (!result.ok) {
      res.status(409).json({ error: "A chat session is already active", sessionKey: result.conflict });
      return;
    }
    // Full SessionMeta (available synchronously — init does not block create).
    res.status(201).json(manager.get(result.sessionKey)?.meta);
  });

  router.get("/sessions", (_req, res) => {
    res.json(manager.list());
  });

  router.get("/sessions/:key", (req, res) => {
    const key = req.params["key"] ?? "";
    const session = manager.get(key);
    if (!session) {
      res.status(404).json({ error: "session not found" });
      return;
    }
    const meta = session.meta;
    res.json({
      meta,
      pendingApprovals: broker.pendingFor(key),
      lastSeq: meta.lastSeq,
    });
  });

  router.post("/sessions/:key/interrupt", (req, res) => {
    const key = req.params["key"] ?? "";
    const session = manager.get(key);
    if (!session) {
      res.status(404).json({ error: "session not found" });
      return;
    }
    void session.interrupt();
    res.json({ ok: true });
  });

  router.delete("/sessions/:key", (req, res) => {
    const key = req.params["key"] ?? "";
    void manager.dispose(key).then((ok) => {
      if (!ok) res.status(404).json({ error: "session not found" });
      else res.json({ ok: true });
    });
  });

  // On-disk session history for a project (SDK listSessions()), mapped to the
  // client shape: bare array of { sdkSessionId, cwd, title, updatedAt }.
  router.get("/history", (req, res) => {
    const cwd = typeof req.query["cwd"] === "string" ? req.query["cwd"] : undefined;
    void listSessions(cwd ? { dir: cwd } : undefined)
      .then((sessions) =>
        res.json(
          sessions.map((s) => ({
            sdkSessionId: s.sessionId,
            cwd: cwd ?? s.cwd ?? "",
            title: s.customTitle ?? s.summary ?? null,
            updatedAt: s.lastModified,
          })),
        ),
      )
      .catch((err: unknown) => res.status(500).json({ error: String(err) }));
  });

  // ---- M2 stubs ---------------------------------------------------------- //
  router.get("/history/:id/messages", (_req, res) => res.status(501).json(M2));
  router.get("/sessions/:key/tool-output/:toolUseId", (_req, res) => res.status(501).json(M2));
  router.get("/jobs", (_req, res) => res.status(501).json(M2));
  router.post("/jobs", (_req, res) => res.status(501).json(M2));
  router.post("/jobs/:id/cancel", (_req, res) => res.status(501).json(M2));
  router.get("/cortex/data", (_req, res) => res.status(501).json({ error: "Not implemented (M3)" }));

  return router;
}

function parseProfile(v: unknown): PermissionProfileName | undefined {
  return v === "chat" || v === "run" ? v : undefined;
}

/** Directory-only autocomplete with ~ expansion; read-only, capped, ENOENT-safe. */
async function suggestDirs(input: string): Promise<string[]> {
  const expanded = expandHome(input || "~");
  const endsWithSep = expanded.endsWith("/");
  const dir = endsWithSep ? expanded : dirname(expanded);
  const prefix = endsWithSep ? "" : basename(expanded);
  try {
    const entries = await readdir(resolve(dir), { withFileTypes: true });
    const out: string[] = [];
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (!entry.name.toLowerCase().startsWith(prefix.toLowerCase())) continue;
      if (!prefix.startsWith(".") && entry.name.startsWith(".")) continue;
      out.push(join(resolve(dir), entry.name));
      if (out.length >= 50) break;
    }
    return out.sort();
  } catch {
    return [];
  }
}

function expandHome(p: string): string {
  if (p === "~") return homedir();
  if (p.startsWith("~/")) return join(homedir(), p.slice(2));
  return p;
}
