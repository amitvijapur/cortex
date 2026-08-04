// Cortex Command — DEV-ONLY demo fixture (activated by ?demo=1).
//
// Bypasses the WS + REST layers and drives the store directly with a canned,
// deterministic sequence of EventEnvelopes that exercises EVERY component:
// session lifecycle, streaming text + thinking, Bash/Edit(diff)/Read tool
// cards, a pending PermissionCard with a live countdown, resolved-approved and
// resolved-timeout permissions, a RoutingCard, a subagent Task with two nested
// child tool calls, TurnResultRows, and cost accumulation across two turns.
//
// The reviewer opens /?demo=1 and watches it play; nothing here ships to prod
// (App only imports it lazily under the flag).

import type {
  HelloMessage,
  PermissionDecision,
  SessionEvent,
  SessionMeta,
} from "@cortex-command/shared";
import {
  applyEnvelope,
  applyHello,
  readState,
  setConnection,
} from "../lib/store";
import type { Client } from "../lib/ws";

const SESSION_KEY = "sess_demo01";

const demoMeta: SessionMeta = {
  sessionKey: SESSION_KEY,
  sdkSessionId: "9f3c1a7e-4b21-4d8a-bc55-2e9a71f0c4d2",
  kind: "chat",
  profile: "chat",
  cwd: "/Users/amit/Desktop/cortex",
  title: "Refactor auth middleware",
  status: "starting",
  model: "claude-opus-4-8",
  createdAt: Date.now(),
  updatedAt: Date.now(),
  lastSeq: 0,
  costUsd: 0,
  jobId: null,
};

// A step is a delay (ms since the previous step) + a factory producing the event.
interface Step {
  delay: number;
  make: (now: number) => SessionEvent;
}

const BIG_OUTPUT = Array.from({ length: 40 }, (_, i) =>
  `  ✓ src/module-${String(i).padStart(2, "0")}.ts  compiled in ${(12 + i * 0.7).toFixed(1)}ms`,
).join("\n");

const FINAL_MD = [
  "I'll refactor the middleware in three steps:",
  "",
  "1. Read the current middleware",
  "2. Swap the ad-hoc token map for `sessionStore`",
  "3. Run the auth tests",
  "",
  "Here's the shape of the new lookup:",
  "",
  "```ts",
  "const user = await sessionStore.get(token);",
  "if (!user) return res.status(401).end();",
  "```",
  "",
  "This removes the in-memory **tokenMap** entirely.",
].join("\n");

const steps: Step[] = [
  // Dwell in "starting" long enough to show the booting composer state (enabled,
  // with the "queued — session is booting" hint) before the runtime hands off to
  // running — mirrors the real deadlock case the composer must not block.
  { delay: 2800, make: () => ({ type: "session.status", status: "running" }) },
  {
    delay: 250,
    make: () => ({
      type: "turn.user",
      text: "Refactor the auth middleware to use the new session store, then run the tests.",
    }),
  },
  {
    delay: 350,
    make: () => ({
      type: "routing.card",
      routing: {
        raw: "OMC > autopilot > executor(opus ∥ sonnet) → Fable QC @ L3",
        system: "OMC",
        pattern: "autopilot",
        agent: "executor(opus) ∥ sonnet → Fable QC",
        parallel: ["executor(opus)", "sonnet"],
        reconciler: "Fable QC",
        tier: "L3",
        tags: "fable=delegate+qc",
      },
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "thinking.delta",
      index: 0,
      text: "Locating the auth middleware and the new session store API. ",
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "thinking.delta",
      index: 0,
      text: "The refactor swaps the ad-hoc token map for sessionStore.get/set.",
    }),
  },
  {
    delay: 250,
    make: () => ({
      type: "thinking.done",
      index: 0,
      text:
        "Locating the auth middleware and the new session store API. The refactor swaps the ad-hoc token map for sessionStore.get/set.",
    }),
  },
  { delay: 300, make: () => ({ type: "text.delta", index: 1, text: "I'll refactor the middleware in three steps:\n\n" }) },
  { delay: 250, make: () => ({ type: "text.delta", index: 1, text: "1. Read the current middleware\n2. Swap the token map\n" }) },
  { delay: 250, make: () => ({ type: "text.delta", index: 1, text: "3. Run the auth tests\n\nLet me start by inspecting the file." }) },
  { delay: 300, make: () => ({ type: "text.done", index: 1, text: FINAL_MD }) },

  // Read tool
  { delay: 350, make: () => ({ type: "tool.start", toolUseId: "t_read1", name: "Read" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_read1",
      name: "Read",
      input: { file_path: "/Users/amit/Desktop/cortex/src/auth/middleware.ts", offset: 1, limit: 40 },
    }),
  },
  {
    delay: 400,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_read1",
      name: "Read",
      isError: false,
      truncated: false,
      preview:
        "export function authMiddleware(req, res, next) {\n  const token = req.headers.authorization;\n  const user = tokenMap[token];\n  if (!user) return res.status(401).end();\n  next();\n}",
    }),
  },

  // Bash tool with big truncated output
  { delay: 350, make: () => ({ type: "tool.start", toolUseId: "t_bash1", name: "Bash" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_bash1",
      name: "Bash",
      input: { command: "npm run build", description: "Type-check the whole project" },
    }),
  },
  {
    delay: 900,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_bash1",
      name: "Bash",
      isError: false,
      truncated: true,
      fullLength: 18234,
      outputRef: "/api/sessions/sess_demo01/tool-output/t_bash1",
      preview: BIG_OUTPUT + "\n\n… (truncated) …\n\n  ✓ built in 1.84s",
    }),
  },

  // Edit tool → DiffCard
  { delay: 350, make: () => ({ type: "tool.start", toolUseId: "t_edit1", name: "Edit" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_edit1",
      name: "Edit",
      input: {
        file_path: "/Users/amit/Desktop/cortex/src/auth/middleware.ts",
        old_string:
          "  const token = req.headers.authorization;\n  const user = tokenMap[token];\n  if (!user) return res.status(401).end();\n  next();",
        new_string:
          "  const token = req.headers.authorization;\n  const user = await sessionStore.get(token);\n  if (!user) return res.status(401).end();\n  req.session = user;\n  next();",
      },
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_edit1",
      name: "Edit",
      isError: false,
      truncated: false,
      preview: "Applied 1 edit to middleware.ts",
    }),
  },

  // Pending permission — risky Bash, left pending so the countdown runs
  { delay: 350, make: () => ({ type: "tool.start", toolUseId: "t_bash2", name: "Bash" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_bash2",
      name: "Bash",
      input: { command: "rm -rf ./dist && npm run test:integration", description: "Clean build then run integration tests" },
    }),
  },
  {
    delay: 250,
    make: (now) => ({
      type: "permission.requested",
      approval: {
        approvalId: "ap_pending",
        sessionKey: SESSION_KEY,
        toolUseId: "t_bash2",
        toolName: "Bash",
        input: { command: "rm -rf ./dist && npm run test:integration" },
        createdAt: now,
        expiresAt: now + 9 * 60 * 1000,
        status: "pending",
      },
    }),
  },

  // Resolved-approved permission
  { delay: 300, make: () => ({ type: "tool.start", toolUseId: "t_bash3", name: "Bash" }) },
  {
    delay: 120,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_bash3",
      name: "Bash",
      input: { command: "npm test -- auth", description: "Run auth unit tests" },
    }),
  },
  {
    delay: 150,
    make: (now) => ({
      type: "permission.requested",
      approval: {
        approvalId: "ap_approved",
        sessionKey: SESSION_KEY,
        toolUseId: "t_bash3",
        toolName: "Bash",
        input: { command: "npm test -- auth" },
        createdAt: now,
        expiresAt: now + 10 * 60 * 1000,
        status: "pending",
      },
    }),
  },
  {
    delay: 500,
    make: () => ({
      type: "permission.resolved",
      approvalId: "ap_approved",
      toolUseId: "t_bash3",
      decision: "approve",
      resolvedBy: "user",
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_bash3",
      name: "Bash",
      isError: false,
      truncated: false,
      preview: "PASS  test/auth.test.ts  (12 tests, 0.8s)",
    }),
  },

  // Resolved-timeout permission (auto-denied)
  { delay: 300, make: () => ({ type: "tool.start", toolUseId: "t_bash4", name: "Bash" }) },
  {
    delay: 120,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_bash4",
      name: "Bash",
      input: { command: "curl -X POST https://example.com/deploy-hook", description: "Trigger the deploy webhook" },
    }),
  },
  {
    delay: 150,
    make: (now) => ({
      type: "permission.requested",
      approval: {
        approvalId: "ap_timeout",
        sessionKey: SESSION_KEY,
        toolUseId: "t_bash4",
        toolName: "Bash",
        input: { command: "curl -X POST https://example.com/deploy-hook" },
        createdAt: now,
        expiresAt: now,
        status: "pending",
      },
    }),
  },
  {
    delay: 400,
    make: () => ({
      type: "permission.resolved",
      approvalId: "ap_timeout",
      toolUseId: "t_bash4",
      decision: "deny",
      resolvedBy: "timeout",
      expired: true,
    }),
  },
  {
    delay: 250,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_bash4",
      name: "Bash",
      isError: true,
      truncated: false,
      preview: "Tool denied: approval expired (default-deny after 60s).",
    }),
  },

  // Subagent Task with two nested child tool calls
  { delay: 350, make: () => ({ type: "tool.start", toolUseId: "t_task1", name: "Task" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_task1",
      name: "Task",
      input: { description: "Audit test coverage", subagent_type: "executor", prompt: "Review the auth tests and report gaps." },
    }),
  },
  {
    delay: 150,
    make: () => ({
      type: "agent.start",
      agentId: "agent_1",
      parentToolUseId: "t_task1",
      agentType: "executor",
      description: "Audit test coverage",
    }),
  },
  { delay: 250, make: () => ({ type: "tool.start", toolUseId: "t_child1", name: "Grep", parentToolUseId: "t_task1" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_child1",
      name: "Grep",
      input: { pattern: "describe\\(", path: "test/" },
      parentToolUseId: "t_task1",
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_child1",
      name: "Grep",
      isError: false,
      truncated: false,
      preview: "test/auth.test.ts: 3 describe blocks",
      parentToolUseId: "t_task1",
    }),
  },
  { delay: 250, make: () => ({ type: "tool.start", toolUseId: "t_child2", name: "Read", parentToolUseId: "t_task1" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_child2",
      name: "Read",
      input: { file_path: "test/auth.test.ts" },
      parentToolUseId: "t_task1",
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_child2",
      name: "Read",
      isError: false,
      truncated: false,
      preview: "describe('authMiddleware', () => { it('rejects missing token', ...) })",
      parentToolUseId: "t_task1",
    }),
  },
  {
    delay: 300,
    make: () => ({
      type: "agent.stop",
      agentId: "agent_1",
      parentToolUseId: "t_task1",
      status: "completed",
      summary: "Coverage solid; one edge case gap noted.",
    }),
  },
  {
    delay: 200,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_task1",
      name: "Task",
      isError: false,
      truncated: false,
      preview: "Subagent complete: coverage solid, 1 gap flagged (expired-session path).",
    }),
  },

  // Final text + turn result (turn 1)
  { delay: 350, make: () => ({ type: "text.delta", index: 5, text: "Done. The middleware now reads from " }) },
  {
    delay: 300,
    make: () => ({
      type: "text.done",
      index: 5,
      text:
        "Done. The middleware now reads from **sessionStore** and the auth tests pass. The subagent flagged one coverage gap on the expired-session path.",
    }),
  },
  {
    delay: 250,
    make: () => ({
      type: "turn.result",
      subtype: "success",
      isError: false,
      costUsd: 0.0342,
      durationMs: 48213,
      numTurns: 7,
      resultText: "Refactored auth middleware to sessionStore; tests pass.",
      usage: { input_tokens: 18422, output_tokens: 2043, cache_read_input_tokens: 120400 },
    }),
  },
  { delay: 150, make: () => ({ type: "session.status", status: "idle" }) },

  // Second turn — proves multi-turn keying + cost accumulation. Block indexes are
  // monotonic per session (they never restart across turns/messages in the real
  // stream), so this turn continues at index 6, keyed distinctly by curTurn.
  { delay: 600, make: () => ({ type: "turn.user", text: "Now bump the version and commit." }) },
  { delay: 150, make: () => ({ type: "session.status", status: "running" }) },
  { delay: 250, make: () => ({ type: "text.delta", index: 6, text: "Bumping the patch version " }) },
  { delay: 250, make: () => ({ type: "text.done", index: 6, text: "Bumping the patch version and committing the refactor." }) },
  { delay: 300, make: () => ({ type: "tool.start", toolUseId: "t_bash5", name: "Bash" }) },
  {
    delay: 150,
    make: () => ({
      type: "tool.input",
      toolUseId: "t_bash5",
      name: "Bash",
      input: { command: "npm version patch && git commit -am 'refactor(auth): use session store'", description: "Bump version and commit" },
    }),
  },
  {
    delay: 500,
    make: () => ({
      type: "tool.result",
      toolUseId: "t_bash5",
      name: "Bash",
      isError: false,
      truncated: false,
      preview: "v0.1.1\n[main a1b2c3d] refactor(auth): use session store\n 1 file changed, 3 insertions(+), 1 deletion(-)",
    }),
  },
  {
    delay: 250,
    make: () => ({
      type: "turn.result",
      subtype: "success",
      isError: false,
      costUsd: 0.0518,
      durationMs: 12044,
      numTurns: 2,
      resultText: "Version bumped to 0.1.1 and changes committed.",
    }),
  },
  { delay: 150, make: () => ({ type: "session.status", status: "idle" }) },
];

/** DemoClient satisfies the Client interface; sends resolve/echo locally. */
export class DemoClient implements Client {
  private seq = 0;
  private started = false;

  private nextSeq(): number {
    return ++this.seq;
  }

  private emit(event: SessionEvent): void {
    applyEnvelope({
      type: "event",
      sessionKey: SESSION_KEY,
      seq: this.nextSeq(),
      ts: Date.now(),
      event,
    });
  }

  start(): void {
    if (this.started) return;
    this.started = true;

    const hello: HelloMessage = {
      type: "hello",
      protocolVersion: 1,
      serverVersion: "demo",
      sessions: [demoMeta],
      jobs: [],
      now: Date.now(),
    };
    applyHello(hello);
    setConnection("open");

    let acc = 0;
    for (const step of steps) {
      acc += step.delay;
      window.setTimeout(() => this.emit(step.make(Date.now())), acc);
    }
  }

  subscribeSession(): void {
    /* no-op in demo */
  }

  sendUserMessage(_sessionKey: string, text: string): void {
    this.emit({ type: "turn.user", text });
    this.emit({ type: "session.status", status: "running" });
    window.setTimeout(() => {
      this.emit({
        type: "text.done",
        index: 0,
        text:
          "This is **demo mode** — replies are canned. Wire the server (drop `?demo=1`) to chat for real.",
      });
      this.emit({
        type: "turn.result",
        subtype: "success",
        isError: false,
        costUsd: 0.0011,
        durationMs: 900,
        numTurns: 1,
      });
      this.emit({ type: "session.status", status: "idle" });
    }, 500);
  }

  sendInterrupt(): void {
    this.emit({ type: "session.status", status: "idle", detail: "interrupted" });
  }

  sendPermissionDecision(approvalId: string, decision: PermissionDecision): void {
    const sess = readState().sessions[SESSION_KEY];
    const ap = sess?.approvals[approvalId];
    if (!ap || ap.status !== "pending") return;
    this.emit({
      type: "permission.resolved",
      approvalId,
      toolUseId: ap.toolUseId,
      decision,
      resolvedBy: "user",
    });
    this.emit({
      type: "tool.result",
      toolUseId: ap.toolUseId,
      name: ap.toolName,
      isError: decision === "deny",
      truncated: false,
      preview:
        decision === "approve"
          ? "PASS  integration suite (34 tests, 6.2s)"
          : "Tool denied by you.",
    });
  }
}
