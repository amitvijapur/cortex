// Cortex Command — M1 server pipeline test (run: npx tsx dev/pipeline-test.ts).
//
// Drives the REAL server (Express + ws hub + SessionManager + EventLog +
// PermissionBroker + translate) against a listening socket using a REAL ws
// client, with an INJECTED scripted fake query stream — no Claude runtime is
// spawned. It exercises, end to end:
//   init → coalesced text deltas → tool_use Bash → canUseTool ask → WS
//   permission.decide allow → tool_result → Task fan-out (parent_tool_use_id) →
//   ResultMessage.
// Assertions: event order, seq monotonicity, replay-from-0 == live stream,
// permission card round-trip, replay-while-pending still shows pending, GET
// pendingApprovals, idempotent double-decide, and the timeout default-deny path
// (with a short injected timeout).
//
// This file lives outside src/ so it is not part of the server build; tsx runs
// it directly (esbuild strips types), so the scripted SDK messages are cast
// loosely on purpose.

import { join } from "node:path";
import { tmpdir } from "node:os";
import { WebSocket } from "ws";
import { createApp } from "../src/index.js";
import { askHookDecision, denyHookDecision, makeAskHook } from "../src/permissions/hooks.js";
import { chatProfile, runProfile } from "../src/permissions/profiles.js";
import { SessionManager } from "../src/session/SessionManager.js";
import type { QueryFactory } from "../src/session/Session.js";

// --------------------------------------------------------------------------- //
// Tiny assert harness
// --------------------------------------------------------------------------- //

let passed = 0;
const failures: string[] = [];
function check(cond: boolean, label: string): void {
  if (cond) {
    passed++;
    console.log(`  ✓ ${label}`);
  } else {
    failures.push(label);
    console.log(`  ✗ ${label}`);
  }
}
function section(name: string): void {
  console.log(`\n▶ ${name}`);
}

// --------------------------------------------------------------------------- //
// Scripted SDK message builders (cast to the SDK shape at the call site)
// --------------------------------------------------------------------------- //

const SDK_ID = "11111111-1111-4111-8111-111111111111";
const init = () =>
  ({ type: "system", subtype: "init", session_id: SDK_ID, model: "claude-test", cwd: tmpdir(), tools: [], mcp_servers: [], slash_commands: [], output_style: "default", skills: [], plugins: [], permissionMode: "default", apiKeySource: "oauth", claude_code_version: "test", uuid: "u", agents: [] } as any);
const textDelta = (text: string, index = 0) =>
  ({ type: "stream_event", parent_tool_use_id: null, uuid: "u", session_id: SDK_ID, event: { type: "content_block_delta", index, delta: { type: "text_delta", text } } } as any);
const thinkingDelta = (text: string, index = 0) =>
  ({ type: "stream_event", parent_tool_use_id: null, uuid: "u", session_id: SDK_ID, event: { type: "content_block_delta", index, delta: { type: "thinking_delta", thinking: text } } } as any);
// Assistant delivery. `opts.id` is the API message.id (real CLI always sets it);
// split deliveries of one message share the same id. Subagent fields optional.
const assistant = (
  content: any[],
  parent: string | null = null,
  opts: { id?: string; subagent_type?: string; task_description?: string } = {},
) => {
  const message: any = { role: "assistant", content };
  if (opts.id) message.id = opts.id;
  const rec: any = { type: "assistant", parent_tool_use_id: parent, uuid: "u", session_id: SDK_ID, message };
  if (opts.subagent_type) rec.subagent_type = opts.subagent_type;
  if (opts.task_description) rec.task_description = opts.task_description;
  return rec;
};
const toolResult = (toolUseId: string, content: string, isError = false) =>
  ({ type: "user", parent_tool_use_id: null, uuid: "u", session_id: SDK_ID, message: { role: "user", content: [{ type: "tool_result", tool_use_id: toolUseId, content, is_error: isError }] } } as any);
const result = () =>
  ({ type: "result", subtype: "success", is_error: false, total_cost_usd: 0.0123, duration_ms: 1500, num_turns: 2, result: "All done", usage: { input_tokens: 10, output_tokens: 20 }, session_id: SDK_ID, uuid: "u", num_turns_api: 1 } as any);
const messageStart = (id: string) =>
  ({ type: "stream_event", parent_tool_use_id: null, uuid: "u", session_id: SDK_ID, event: { type: "message_start", message: { id } } } as any);
const cbStart = (index: number, block: any) =>
  ({ type: "stream_event", parent_tool_use_id: null, uuid: "u", session_id: SDK_ID, event: { type: "content_block_start", index, content_block: block } } as any);
const cbStop = (index: number) =>
  ({ type: "stream_event", parent_tool_use_id: null, uuid: "u", session_id: SDK_ID, event: { type: "content_block_stop", index } } as any);

function attachInterrupt(gen: any): any {
  gen.interrupt = async () => undefined;
  return gen;
}

async function firstUserTurn(prompt: AsyncIterable<any>): Promise<boolean> {
  const it = prompt[Symbol.asyncIterator]();
  const first = await it.next();
  return !first.done;
}

/** Main happy-path fake: streams a full turn, blocking on canUseTool for Bash. */
const mainFake: QueryFactory = ({ prompt, options }) => {
  async function* gen(): AsyncGenerator<any, void> {
    yield init();
    if (!(await firstUserTurn(prompt))) return;
    yield messageStart("msg_main");
    yield textDelta("Hel");
    yield textDelta("lo ");
    yield textDelta("world");
    yield assistant(
      [
        { type: "text", text: "Hello world" },
        { type: "tool_use", id: "tu_bash", name: "Bash", input: { command: "ls" } },
      ],
      null,
      { id: "msg_main" },
    );
    const decision = await options.canUseTool!(
      "Bash",
      { command: "ls" },
      { signal: new AbortController().signal, toolUseID: "tu_bash", requestId: "r1", suggestions: [] } as any,
    );
    if (decision.behavior === "allow") yield toolResult("tu_bash", "file1\nfile2", false);
    else yield toolResult("tu_bash", decision.message, true);
    // Subagent fan-out under a Task tool call (separate API messages).
    yield assistant([{ type: "tool_use", id: "tu_task", name: "Task", input: { subagent_type: "executor", description: "do subtask" } }], null, { id: "msg_task" });
    yield assistant([{ type: "text", text: "sub working" }], "tu_task", { id: "msg_sub", subagent_type: "executor", task_description: "do subtask" });
    yield toolResult("tu_task", "subagent done", false);
    yield result();
  }
  return attachInterrupt(gen());
};

/** Timeout fake: asks for Bash and never gets an answer → default-deny fires. */
const timeoutFake: QueryFactory = ({ prompt, options }) => {
  async function* gen(): AsyncGenerator<any, void> {
    yield init();
    if (!(await firstUserTurn(prompt))) return;
    yield assistant([{ type: "tool_use", id: "tu_bash2", name: "Bash", input: { command: "whoami" } }], null, { id: "msg_to" });
    const decision = await options.canUseTool!(
      "Bash",
      { command: "whoami" },
      { signal: new AbortController().signal, toolUseID: "tu_bash2", requestId: "r2", suggestions: [] } as any,
    );
    yield toolResult("tu_bash2", decision.behavior === "deny" ? decision.message : "ran", decision.behavior === "deny");
    yield result();
  }
  return attachInterrupt(gen());
};

/** Dedup fake: delivers ONE tool block via BOTH partial start AND the full msg. */
const dedupFake: QueryFactory = ({ prompt }) => {
  async function* gen(): AsyncGenerator<any, void> {
    yield init();
    if (!(await firstUserTurn(prompt))) return;
    yield messageStart("msg_dup");
    yield cbStart(0, { type: "tool_use", id: "tu_dup", name: "Read", input: {} });
    yield cbStop(0);
    yield assistant([{ type: "tool_use", id: "tu_dup", name: "Read", input: { file_path: "/x" } }], null, { id: "msg_dup" });
    yield toolResult("tu_dup", "contents", false);
    yield result();
  }
  return attachInterrupt(gen());
};

/** Index fake: two SEPARATE API messages, each with text at sdk-index 0. */
const indexFake: QueryFactory = ({ prompt }) => {
  async function* gen(): AsyncGenerator<any, void> {
    yield init();
    if (!(await firstUserTurn(prompt))) return;
    // Message A (partials): text@0, then full [text@0, tool_use@1].
    yield messageStart("msg_a");
    yield textDelta("first", 0);
    yield assistant(
      [
        { type: "text", text: "first" },
        { type: "tool_use", id: "tu_r", name: "Read", input: { file_path: "/a" } },
      ],
      null,
      { id: "msg_a" },
    );
    yield toolResult("tu_r", "ok", false);
    // Message B (partials): text again at sdk-index 0 — must NOT collide with A.
    yield messageStart("msg_b");
    yield textDelta("second", 0);
    yield assistant([{ type: "text", text: "second" }], null, { id: "msg_b" });
    yield result();
  }
  return attachInterrupt(gen());
};

/**
 * Split-delivery fake: replicates the REAL observed sequence (raw-dump.ts) — ONE
 * API message.id split into TWO deliveries ([thinking] then [text]) while the
 * partial stream carries continuous API indexes 0 then 1.
 */
const splitFake: QueryFactory = ({ prompt }) => {
  const M = "msg_split_1";
  async function* gen(): AsyncGenerator<any, void> {
    yield init();
    if (!(await firstUserTurn(prompt))) return;
    yield messageStart(M);
    yield cbStart(0, { type: "thinking" });
    yield thinkingDelta("2 plus 2 is 4", 0);
    yield cbStop(0);
    yield assistant([{ type: "thinking", thinking: "2 plus 2 is 4", signature: "sig" }], null, { id: M }); // delivery #1
    yield cbStart(1, { type: "text" });
    yield textDelta("The answer is 4", 1);
    yield cbStop(1);
    yield assistant([{ type: "text", text: "The answer is 4" }], null, { id: M }); // delivery #2, SAME id
    yield result();
  }
  return attachInterrupt(gen());
};

// --------------------------------------------------------------------------- //
// WS client helper
// --------------------------------------------------------------------------- //

interface Client {
  ws: WebSocket;
  frames: any[];
  send(msg: any): void;
  waitFor(pred: (f: any) => boolean, ms?: number): Promise<any>;
  close(): void;
}

function connect(port: number): Promise<Client> {
  return new Promise((resolveConn, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`);
    const frames: any[] = [];
    ws.on("message", (d) => frames.push(JSON.parse(d.toString())));
    ws.on("error", reject);
    ws.on("open", () => {
      resolveConn({
        ws,
        frames,
        send: (msg) => ws.send(JSON.stringify(msg)),
        waitFor: (pred, ms = 3000) =>
          new Promise((res, rej) => {
            const existing = frames.find(pred);
            if (existing) return res(existing);
            const timer = setTimeout(() => {
              ws.off("message", onMsg);
              rej(new Error("waitFor timed out"));
            }, ms);
            const onMsg = (d: any) => {
              const f = JSON.parse(d.toString());
              if (pred(f)) {
                clearTimeout(timer);
                ws.off("message", onMsg);
                res(f);
              }
            };
            ws.on("message", onMsg);
          }),
        close: () => ws.close(),
      });
    });
  });
}

const isEvent = (t: string) => (f: any) => f.type === "event" && f.event?.type === t;
const eventsOf = (frames: any[]) => frames.filter((f) => f.type === "event");
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// --------------------------------------------------------------------------- //
// Test body
// --------------------------------------------------------------------------- //

const isAsk = (o: any) => o?.hookSpecificOutput?.permissionDecision === "ask";
const isDeny = (o: any) => o?.hookSpecificOutput?.permissionDecision === "deny";
const noOpinion = (o: any) => !o?.hookSpecificOutput;

async function run(): Promise<void> {
  const cwd = tmpdir();

  // ---- PreToolUse ask-hook (settings-shadow guard) — pure unit tests ------ //
  // These need no server: the SDK can't run hook plumbing against a fake query,
  // so the decision cores are tested directly.
  section("PreToolUse ask-hook (settings-file allow-rule shadow guard)");
  const chat = chatProfile(cwd);
  const run_ = runProfile(cwd);
  const inCwdEdit = { file_path: join(cwd, "src/x.ts") };
  const outCwdEdit = { file_path: "/etc/passwd" };
  const escapeEdit = { file_path: join(cwd, "../../etc/shadow") };

  check(isAsk(askHookDecision(chat, cwd, "Bash", { command: "ls -la" })), "chat: Bash → ask (forced past settings allow rules)");
  check(noOpinion(askHookDecision(chat, cwd, "Read", { file_path: "/anywhere" })), "chat: Read → no opinion (auto-approved)");
  check(noOpinion(askHookDecision(chat, cwd, "Grep", { pattern: "x" })), "chat: Grep → no opinion");
  check(noOpinion(askHookDecision(chat, cwd, "Edit", inCwdEdit)), "chat: in-cwd Edit → no opinion");
  check(isAsk(askHookDecision(chat, cwd, "Edit", outCwdEdit)), "chat: out-of-cwd Edit → ask");
  check(isAsk(askHookDecision(chat, cwd, "Edit", escapeEdit)), "chat: `..`-escaping Edit → ask");
  check(noOpinion(askHookDecision(chat, cwd, "NotebookEdit", { notebook_path: join(cwd, "nb.ipynb") })), "chat: in-cwd NotebookEdit → no opinion");
  check(isAsk(askHookDecision(chat, cwd, "mcp__supabase__execute_sql", {})), "chat: mcp__* tool → ask");
  check(isAsk(askHookDecision(chat, cwd, "WeirdUnknownTool", {})), "chat: unknown tool → ask");

  check(noOpinion(askHookDecision(run_, cwd, "Bash", { command: "ls" })), "run: Bash → no opinion (broad Bash auto-runs)");
  check(isDeny(denyHookDecision(run_, "Bash", { command: "sudo rm -rf /" })), "run: sudo → deny (denylist)");
  check(noOpinion(denyHookDecision(run_, "Bash", { command: "ls" })), "run: benign Bash → no opinion from deny hook");
  check(noOpinion(denyHookDecision(chat, "Bash", { command: "sudo x" })), "chat: deny hook is inert (no denyPatterns)");

  // Exercise the wrapped matcher callback (real HookCallback signature).
  const askCb = makeAskHook(chat, cwd).hooks[0] as any;
  const cbOut = await askCb({ hook_event_name: "PreToolUse", tool_name: "Bash", tool_input: { command: "ls" } }, undefined, { signal: new AbortController().signal });
  check(isAsk(cbOut), "ask-hook matcher callback returns ask for Bash on chat");
  const cbNonPre = await askCb({ hook_event_name: "SessionStart" }, undefined, { signal: new AbortController().signal });
  check(noOpinion(cbNonPre), "ask-hook matcher callback is a no-op for non-PreToolUse input");

  // ---- buildOptions attaches the hooks for BOTH profiles ------------------ //
  // Capture the Options the SDK factory receives (no runtime spawned).
  section("buildOptions wires PreToolUse hooks for both profiles");
  {
    let optsChat: any;
    let optsRun: any;
    const idleFactory = (sink: (o: any) => void): QueryFactory => ({ options }) => {
      sink(options);
      const g = (async function* (): AsyncGenerator<any, void> {})() as any;
      g.interrupt = async () => undefined;
      return g;
    };
    const mgr = new SessionManager({ broadcast: () => {} });
    mgr.create({ cwd, kind: "chat", queryFactory: idleFactory((o) => (optsChat = o)) });
    mgr.create({ cwd, kind: "run", queryFactory: idleFactory((o) => (optsRun = o)) });
    check(optsChat?.hooks?.PreToolUse?.length === 1, "chat buildOptions → 1 PreToolUse hook (ask only)");
    check(optsRun?.hooks?.PreToolUse?.length === 2, "run buildOptions → 2 PreToolUse hooks (deny then ask)");
    const runFirst = optsRun?.hooks?.PreToolUse?.[0]?.hooks?.[0];
    const denyOut = await runFirst({ hook_event_name: "PreToolUse", tool_name: "Bash", tool_input: { command: "sudo rm -rf /" } }, undefined, { signal: new AbortController().signal });
    check(isDeny(denyOut), "run PreToolUse[0] is the DENY hook (deny wins, runs first)");
    const chatFirst = optsChat?.hooks?.PreToolUse?.[0]?.hooks?.[0];
    const chatOut = await chatFirst({ hook_event_name: "PreToolUse", tool_name: "Bash", tool_input: { command: "ls" } }, undefined, { signal: new AbortController().signal });
    check(isAsk(chatOut), "chat PreToolUse[0] is the ASK hook (Bash → ask)");
    await mgr.disposeAll();
  }

  const handle = createApp({ defaultQueryFactory: mainFake, serveStatic: false });
  const port = await handle.listen(0);
  const base = `http://127.0.0.1:${port}`;
  console.log(`server listening on ${port} (cwd=${cwd})`);

  // ---- happy path -------------------------------------------------------- //
  section("session create + subscribe");
  const a = await connect(port);
  await a.waitFor((f) => f.type === "hello");
  check(true, "client received hello");

  const createRes = await fetch(`${base}/api/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ cwd }),
  });
  const { sessionKey } = (await createRes.json()) as any;
  check(createRes.status === 201 && typeof sessionKey === "string", "POST /api/sessions → 201 + sessionKey");

  a.send({ type: "sub", channels: [{ sessionKey, sinceSeq: 0 }] });
  const replayStart = await a.waitFor((f) => f.type === "replay.start" && f.sessionKey === sessionKey);
  await a.waitFor((f) => f.type === "replay.end" && f.sessionKey === sessionKey);
  check(replayStart.truncated === false, "replay bracket delivered (no truncation)");

  section("409 conflict on second chat session");
  const conflictRes = await fetch(`${base}/api/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ cwd }),
  });
  const conflictBody = (await conflictRes.json()) as any;
  check(conflictRes.status === 409 && conflictBody.sessionKey === sessionKey, "second chat session → 409 with existing sessionKey");

  section("user turn → coalesced deltas → tool + permission ask");
  a.send({ type: "user.message", sessionKey, text: "hi", clientMsgId: "c1" });
  const requested = await a.waitFor(isEvent("permission.requested"));
  const approval = requested.event.approval;
  check(approval.toolName === "Bash", "permission.requested for Bash");
  check((approval.input as any).command === "ls", "approval carries the Bash command");

  const textDeltas = eventsOf(a.frames).filter((f) => f.event.type === "text.delta");
  check(textDeltas.length === 1, "3 raw deltas coalesced into 1 text.delta");
  check(textDeltas[0]?.event.text === "Hello world", "coalesced delta text == 'Hello world'");

  section("pending state visible via REST + replay-while-pending");
  const getRes = await fetch(`${base}/api/sessions/${sessionKey}`);
  const getBody = (await getRes.json()) as any;
  check(getBody.pendingApprovals?.length === 1, "GET /api/sessions/:key shows 1 pendingApproval");
  check(getBody.meta.status === "awaiting_permission", "session status == awaiting_permission");

  const b = await connect(port);
  await b.waitFor((f) => f.type === "hello");
  b.send({ type: "sub", channels: [{ sessionKey, sinceSeq: 0 }] });
  await b.waitFor((f) => f.type === "replay.end" && f.sessionKey === sessionKey);
  const bEvents = eventsOf(b.frames);
  const bReq = bEvents.filter((f) => f.event.type === "permission.requested");
  const bResolved = bEvents.filter((f) => f.event.type === "permission.resolved");
  check(bReq.length === 1 && bResolved.length === 0, "replay after a pending permission still shows it pending");
  b.close();

  section("decide allow → tool_result → fan-out → result");
  a.send({ type: "permission.decide", approvalId: approval.approvalId, decision: "approve" });
  const resolved = await a.waitFor(isEvent("permission.resolved"));
  check(resolved.event.decision === "approve" && resolved.event.resolvedBy === "user", "permission.resolved approve by user");

  const turnResult = await a.waitFor(isEvent("turn.result"));
  check(turnResult.event.subtype === "success", "turn.result subtype success");
  check(Math.abs(turnResult.event.costUsd - 0.0123) < 1e-9, "turn.result carries cost");

  section("idempotent double-decide");
  a.send({ type: "permission.decide", approvalId: approval.approvalId, decision: "deny" });
  await delay(150);
  const resolvedCount = eventsOf(a.frames).filter((f) => f.event.type === "permission.resolved").length;
  check(resolvedCount === 1, "second decide is a no-op (exactly 1 permission.resolved)");

  section("event ordering + seq monotonicity");
  const ev = eventsOf(a.frames);
  const seqs = ev.map((f) => f.seq);
  const monotonic = seqs.every((s, i) => i === 0 || s > seqs[i - 1]);
  check(monotonic, "seq strictly increases across all events");

  const idx = (t: string, match?: (e: any) => boolean) =>
    ev.findIndex((f) => f.event.type === t && (!match || match(f.event)));
  const order = [
    idx("turn.user"),
    idx("text.delta"),
    idx("text.done"),
    idx("tool.start", (e) => e.name === "Bash"),
    idx("tool.input", (e) => e.name === "Bash"),
    idx("permission.requested"),
    idx("permission.resolved"),
    idx("tool.result", (e) => e.toolUseId === "tu_bash"),
    idx("turn.result"),
  ];
  const ordered = order.every((v, i) => v >= 0 && (i === 0 || v > order[i - 1]));
  check(ordered, "canonical event order holds (user→text→tool→ask→resolve→result→turn.result)");

  section("subagent fan-out tagging");
  const agentStart = ev.find((f) => f.event.type === "agent.start");
  check(agentStart?.event.parentToolUseId === "tu_task", "agent.start anchored to Task tool_use id");
  check(agentStart?.event.description === "do subtask", "agent.start enriched with task_description");
  const subText = ev.find((f) => f.event.type === "text.done" && f.event.parentToolUseId === "tu_task");
  check(!!subText, "subagent text.done carries parentToolUseId");
  const agentStop = ev.find((f) => f.event.type === "agent.stop" && f.event.parentToolUseId === "tu_task");
  check(!!agentStop, "agent.stop paired to the Task tool_result");

  section("replay-from-0 == live stream");
  const c = await connect(port);
  await c.waitFor((f) => f.type === "hello");
  c.send({ type: "sub", channels: [{ sessionKey, sinceSeq: 0 }] });
  await c.waitFor((f) => f.type === "replay.end" && f.sessionKey === sessionKey);
  const live = eventsOf(a.frames).map((f) => `${f.seq}:${JSON.stringify(f.event)}`);
  const replayed = eventsOf(c.frames).map((f) => `${f.seq}:${JSON.stringify(f.event)}`);
  check(replayed.length === live.length && replayed.every((s, i) => s === live[i]), "full replay from seq 0 equals the live stream");
  c.close();

  section("interrupt endpoint");
  const interruptRes = await fetch(`${base}/api/sessions/${sessionKey}/interrupt`, { method: "POST" });
  check(interruptRes.status === 200, "POST /api/sessions/:key/interrupt → 200");

  section("DELETE frees the chat slot");
  const delRes = await fetch(`${base}/api/sessions/${sessionKey}`, { method: "DELETE" });
  check(delRes.status === 200, "DELETE disposes the chat session (frees the slot)");

  section("dedup: same tool block via partial + full → one tool.start");
  const cDedup = handle.manager.create({ cwd, queryFactory: dedupFake });
  const keyDup = cDedup.ok ? cDedup.sessionKey : "";
  a.send({ type: "sub", channels: [{ sessionKey: keyDup, sinceSeq: 0 }] });
  await a.waitFor((f) => f.type === "replay.end" && f.sessionKey === keyDup);
  a.send({ type: "user.message", sessionKey: keyDup, text: "read the file" });
  await a.waitFor((f) => isEvent("turn.result")(f) && f.sessionKey === keyDup);
  const dupStarts = eventsOf(a.frames).filter(
    (f) => f.sessionKey === keyDup && f.event.type === "tool.start" && f.event.toolUseId === "tu_dup",
  );
  check(dupStarts.length === 1, "tool block via partial + full yields exactly one tool.start (no duplicate)");
  await handle.manager.dispose(keyDup);

  section("block index: multi-message turn keeps text blocks distinct");
  const cIdx = handle.manager.create({ cwd, queryFactory: indexFake });
  const keyIdx = cIdx.ok ? cIdx.sessionKey : "";
  a.send({ type: "sub", channels: [{ sessionKey: keyIdx, sinceSeq: 0 }] });
  await a.waitFor((f) => f.type === "replay.end" && f.sessionKey === keyIdx);
  a.send({ type: "user.message", sessionKey: keyIdx, text: "go" });
  await a.waitFor((f) => isEvent("turn.result")(f) && f.sessionKey === keyIdx);
  const idxEv = eventsOf(a.frames).filter((f) => f.sessionKey === keyIdx);
  const dones = idxEv.filter((f) => f.event.type === "text.done");
  check(dones.length === 2, "two text.done across the multi-message turn");
  const dIdx = dones.map((f) => f.event.index);
  check(dIdx[0] !== dIdx[1], `the two text.done carry distinct indexes (got ${dIdx.join(",")})`);
  const iDeltas = idxEv.filter((f) => f.event.type === "text.delta");
  const pairOk = dones.every((d) =>
    iDeltas.some((dl) => dl.event.index === d.event.index && dl.event.text === d.event.text),
  );
  check(pairOk, "each text.done pairs with a same-index delta of identical text (delta/done invariant)");
  await handle.manager.dispose(keyIdx);

  section("split delivery: ONE message.id → [thinking] then [text] (real CLI shape)");
  const cSplit = handle.manager.create({ cwd, queryFactory: splitFake });
  const keySplit = cSplit.ok ? cSplit.sessionKey : "";
  a.send({ type: "sub", channels: [{ sessionKey: keySplit, sinceSeq: 0 }] });
  await a.waitFor((f) => f.type === "replay.end" && f.sessionKey === keySplit);
  a.send({ type: "user.message", sessionKey: keySplit, text: "2+2?" });
  await a.waitFor((f) => isEvent("turn.result")(f) && f.sessionKey === keySplit);
  const spEv = eventsOf(a.frames).filter((f) => f.sessionKey === keySplit);
  const thDone = spEv.filter((f) => f.event.type === "thinking.done");
  const txDone = spEv.filter((f) => f.event.type === "text.done");
  const thDelta = spEv.filter((f) => f.event.type === "thinking.delta");
  const txDelta = spEv.filter((f) => f.event.type === "text.delta");
  check(thDone.length === 1 && txDone.length === 1, "split turn yields exactly one thinking.done and one text.done");
  check(
    thDone[0]?.event.index === thDelta[0]?.event.index,
    `thinking.done index (${thDone[0]?.event.index}) == its delta index (${thDelta[0]?.event.index})`,
  );
  check(
    txDone[0]?.event.index === txDelta[0]?.event.index,
    `text.done index (${txDone[0]?.event.index}) == its delta index (${txDelta[0]?.event.index}) — the duplicate-render bug`,
  );
  check(
    txDone[0]?.event.index !== thDone[0]?.event.index,
    "the text block and thinking block land at distinct indexes (no overwrite)",
  );
  // No orphan .done: every streamed .done pairs to a same-index delta.
  const allPaired = [...thDone, ...txDone].every((d) =>
    [...thDelta, ...txDelta].some((dl) => dl.event.index === d.event.index),
  );
  check(allPaired, "no duplicate: every split-delivery .done has a matching same-index delta");
  await handle.manager.dispose(keySplit);

  // ---- timeout default-deny --------------------------------------------- //
  section("timeout default-deny (short injected window)");
  const created = handle.manager.create({ cwd, queryFactory: timeoutFake, approvalTimeoutMs: 150 });
  check(created.ok, "created a fresh session with a 150ms approval timeout");
  const key2 = created.ok ? created.sessionKey : "";
  a.send({ type: "sub", channels: [{ sessionKey: key2, sinceSeq: 0 }] });
  await a.waitFor((f) => f.type === "replay.end" && f.sessionKey === key2);
  a.send({ type: "user.message", sessionKey: key2, text: "run whoami" });
  const req2 = await a.waitFor((f) => isEvent("permission.requested")(f) && f.sessionKey === key2);
  check(req2.event.approval.toolName === "Bash", "second session raises a Bash approval");
  const res2 = await a.waitFor((f) => isEvent("permission.resolved")(f) && f.sessionKey === key2, 3000);
  check(res2.event.expired === true, "unanswered approval auto-denies (expired=true)");
  check(res2.event.decision === "deny" && res2.event.resolvedBy === "timeout", "timeout resolution is deny/timeout");

  a.close();
  await handle.close();

  // ---- summary ---------------------------------------------------------- //
  console.log(`\n${"─".repeat(56)}`);
  console.log(`PASSED ${passed} / ${passed + failures.length}`);
  if (failures.length) {
    console.log("FAILURES:");
    for (const f of failures) console.log(`  - ${f}`);
    process.exit(1);
  }
  console.log("ALL PIPELINE ASSERTIONS PASSED");
  process.exit(0);
}

run().catch((err) => {
  console.error("pipeline test crashed:", err);
  process.exit(2);
});
