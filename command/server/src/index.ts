// Cortex Command — server entrypoint (M1).
//
// Composes the HTTP API (Express) + the WS hub over one Node http server bound
// to 127.0.0.1:7788, wiring the SessionManager / PermissionBroker / EventLog
// pipeline built in ./session and ./permissions. `createApp()` is exported so
// tests can inject a fake queryFactory and drive the whole stack against a real
// listening socket without spawning a Claude runtime. `main()` runs the real
// server when this module is the entrypoint.

import { existsSync } from "node:fs";
import { createServer, type Server as HttpServer } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import express, { type Express } from "express";
import { DEFAULT_PORT, HOST, SERVER_VERSION } from "./config.js";
import { createApiRouter } from "./http/routes.js";
import { SessionManager } from "./session/SessionManager.js";
import type { QueryFactory } from "./session/Session.js";
import { WsHub } from "./ws/hub.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// server/dist/index.js (or server/src/index.ts under tsx) → ../../web/dist
const WEB_DIST = join(__dirname, "..", "..", "web", "dist");

export interface CreateAppDeps {
  /** Inject a fake for tests; defaults to the real SDK query. */
  defaultQueryFactory?: QueryFactory;
  /** Serve the built SPA (default: only if web/dist exists). */
  serveStatic?: boolean;
}

export interface AppHandle {
  app: Express;
  httpServer: HttpServer;
  manager: SessionManager;
  hub: WsHub;
  listen(port: number): Promise<number>;
  close(): Promise<void>;
}

export function createApp(deps: CreateAppDeps = {}): AppHandle {
  let hub: WsHub | undefined;

  const manager = new SessionManager({
    broadcast: (env) => hub?.broadcastEvent(env),
    ...(deps.defaultQueryFactory ? { defaultQueryFactory: deps.defaultQueryFactory } : {}),
  });

  const app = express();
  app.use(express.json({ limit: "8mb" }));
  app.use("/api", createApiRouter({ manager, broker: manager.broker }));

  const shouldServe = deps.serveStatic ?? existsSync(WEB_DIST);
  if (shouldServe) {
    app.use(express.static(WEB_DIST));
    // SPA history fallback for non-/api routes.
    app.get(/^(?!\/api\/).*/, (_req, res) => {
      res.sendFile(join(WEB_DIST, "index.html"));
    });
  }

  const httpServer = createServer(app);
  hub = new WsHub({ server: httpServer, manager, broker: manager.broker });
  const boundHub = hub;

  return {
    app,
    httpServer,
    manager,
    hub: boundHub,
    listen(port: number): Promise<number> {
      return new Promise((resolvePromise, reject) => {
        httpServer.once("error", reject);
        httpServer.listen(port, HOST, () => {
          httpServer.off("error", reject);
          const addr = httpServer.address();
          const actual = typeof addr === "object" && addr ? addr.port : port;
          resolvePromise(actual);
        });
      });
    },
    async close(): Promise<void> {
      await manager.disposeAll();
      await boundHub.close();
      await new Promise<void>((res) => httpServer.close(() => res()));
    },
  };
}

function parsePort(argv: string[]): number {
  const i = argv.indexOf("--port");
  if (i !== -1) {
    const raw = argv[i + 1];
    if (raw) {
      const n = Number(raw);
      if (Number.isInteger(n) && n > 0 && n < 65536) return n;
    }
  }
  return DEFAULT_PORT;
}

async function main(): Promise<void> {
  const handle = createApp();
  const port = parsePort(process.argv.slice(2));
  await handle.listen(port);
  console.log(`cortex-command server (${SERVER_VERSION}) on http://${HOST}:${port}/`);
  if (existsSync(WEB_DIST)) console.log(`  serving web from ${WEB_DIST}`);

  let shuttingDown = false;
  const shutdown = (signal: string): void => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`\n${signal} — disposing sessions, closing WS…`);
    void handle.close().then(() => process.exit(0));
    // Hard cap so a wedged child can't hang shutdown.
    setTimeout(() => process.exit(0), 5000).unref();
  };
  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

// Run only when invoked directly (not when imported by a test).
const invokedPath = process.argv[1];
if (invokedPath && pathToFileURL(invokedPath).href === import.meta.url) {
  void main();
}
