// Cortex Command — Session: one Claude Code runtime bridged to the event log.
//
// A Session owns exactly one `query()` handle fed by a streaming InputQueue
// (multi-turn without re-spawning), a single consumer loop that maps every SDK
// message through translate.ts, a delta Coalescer, a ring-buffer EventLog, and a
// status machine. It implements PermissionSessionSink so the broker can raise
// approval cards into its log.
//
// Cold-start policy (from the SDK research): booting with full settingSources
// spins the entire MCP fleet (~72 processes, minutes). So the query is created
// and its consumer loop started immediately, but NOTHING blocks on init —
// session.status "starting" is emitted synchronously on create and the HTTP/WS
// caller returns at once; init flips status to idle when it lands. Idle chat
// sessions are never disposed implicitly (they stay warm).

import { query } from "@anthropic-ai/claude-agent-sdk";
import type {
  HookCallbackMatcher,
  Options,
  SDKMessage,
  SDKUserMessage,
} from "@anthropic-ai/claude-agent-sdk";
import type {
  EventEnvelope,
  PermissionProfile,
  SessionEvent,
  SessionKind,
  SessionMeta,
  SessionStatus,
} from "@cortex-command/shared";
import type { PermissionBroker, PermissionSessionSink } from "../permissions/PermissionBroker.js";
import { makeAskHook, makeDenyHook } from "../permissions/hooks.js";
import { Coalescer } from "./coalescer.js";
import { EventLog } from "./EventLog.js";
import { InputQueue } from "./inputQueue.js";
import { newTranslateState, translate, type TranslateState } from "./translate.js";

/** The subset of the SDK Query that Session actually uses (test-injectable). */
export interface QueryLike extends AsyncGenerator<SDKMessage, void> {
  interrupt(): Promise<unknown>;
}

export type QueryFactory = (params: {
  prompt: AsyncIterable<SDKUserMessage>;
  options: Options;
}) => QueryLike;

/** Default factory: the real SDK query. */
export const defaultQueryFactory: QueryFactory = (params) =>
  query(params) as unknown as QueryLike;

export interface SessionDeps {
  key: string;
  cwd: string;
  kind: SessionKind;
  profile: PermissionProfile;
  broker: PermissionBroker;
  broadcast: (env: EventEnvelope) => void;
  queryFactory?: QueryFactory;
  title?: string | null;
  /** SDK session_id to resume (crash recovery / history reopen). */
  resumeSdkSessionId?: string | null;
  /** When false, boot with zero MCP servers (A/B init cost). */
  mcp?: boolean;
  jobId?: string | null;
  /** Override the profile timeout (tests use a short window). */
  approvalTimeoutMs?: number;
}

export class Session implements PermissionSessionSink {
  readonly key: string;
  readonly cwd: string;
  readonly kind: SessionKind;
  readonly profile: PermissionProfile;
  readonly approvalTimeoutMs: number;

  private readonly broker: PermissionBroker;
  private readonly broadcast: (env: EventEnvelope) => void;
  private readonly queryFactory: QueryFactory;
  private readonly mcp: boolean;
  private readonly resumeSdkSessionId: string | null;

  private readonly log: EventLog;
  private readonly coalescer: Coalescer;
  private readonly inputQueue = new InputQueue();
  private readonly tstate: TranslateState = newTranslateState();

  private query: QueryLike | null = null;
  private status: SessionStatus = "starting";
  private turnInFlight = false;
  private costUsd = 0;
  private sdkSessionId: string | null = null;
  private model: string | null = null;
  private title: string | null;
  private readonly jobId: string | null;
  private readonly createdAt = Date.now();
  private updatedAt = Date.now();

  constructor(deps: SessionDeps) {
    this.key = deps.key;
    this.cwd = deps.cwd;
    this.kind = deps.kind;
    this.profile = deps.profile;
    this.broker = deps.broker;
    this.broadcast = deps.broadcast;
    this.queryFactory = deps.queryFactory ?? defaultQueryFactory;
    this.title = deps.title ?? null;
    this.resumeSdkSessionId = deps.resumeSdkSessionId ?? null;
    this.mcp = deps.mcp ?? true;
    this.jobId = deps.jobId ?? null;
    this.approvalTimeoutMs = deps.approvalTimeoutMs ?? deps.profile.approvalTimeoutMs;
    this.log = new EventLog(this.key);
    this.coalescer = new Coalescer((event) => this.logEvent(event));
  }

  // ----------------------------------------------------------------------- //
  // Lifecycle
  // ----------------------------------------------------------------------- //

  /** Emit the initial status and boot the runtime child + consumer loop. */
  start(): void {
    this.logEvent({ type: "session.status", status: "starting" });
    this.query = this.queryFactory({
      prompt: this.inputQueue,
      options: this.buildOptions(),
    });
    void this.consume();
  }

  private async consume(): Promise<void> {
    if (!this.query) return;
    try {
      for await (const msg of this.query) {
        this.handleMessage(msg);
      }
    } catch (err) {
      if (this.status !== "disposed") {
        this.coalescer.flushAll();
        this.logEvent({ type: "session.error", message: errorText(err), fatal: true });
        this.setStatus("error");
      }
    }
  }

  private handleMessage(msg: SDKMessage): void {
    // init: capture identity + flip to ready. Not routed through translate.
    if (msg.type === "system" && msg.subtype === "init") {
      this.sdkSessionId = msg.session_id;
      this.model = msg.model;
      if (this.status === "starting") this.setStatus("idle");
      else this.recomputeStatus();
      return;
    }

    const events = translate(msg, this.tstate);
    for (const event of events) {
      if (event.type === "text.delta" || event.type === "thinking.delta") {
        this.coalescer.push(event);
        continue;
      }
      // Any non-delta event: flush buffered deltas first so ordering holds
      // (a delta must never land after its block's .done).
      this.coalescer.flushAll();
      this.logEvent(event);
      if (event.type === "turn.result") this.onTurnComplete(event.costUsd);
    }
  }

  private onTurnComplete(costUsd: number): void {
    this.costUsd += costUsd;
    this.turnInFlight = false;
    if (this.kind === "run") {
      this.setStatus("completed");
    } else {
      this.recomputeStatus();
    }
  }

  // ----------------------------------------------------------------------- //
  // Input
  // ----------------------------------------------------------------------- //

  pushUserMessage(text: string, clientMsgId?: string): void {
    if (this.status === "disposed" || this.status === "error") return;
    this.turnInFlight = true;
    this.logEvent({
      type: "turn.user",
      text,
      ...(clientMsgId !== undefined ? { clientMsgId } : {}),
    });
    this.setStatus("running");
    this.inputQueue.push(this.makeSDKUserMessage(text));
  }

  private makeSDKUserMessage(text: string): SDKUserMessage {
    return {
      type: "user",
      message: { role: "user", content: text },
      parent_tool_use_id: null,
      session_id: this.sdkSessionId ?? "",
    } as SDKUserMessage;
  }

  async interrupt(): Promise<void> {
    try {
      await this.query?.interrupt();
    } catch {
      // best-effort; a completed/aborted query may reject
    }
  }

  async dispose(): Promise<void> {
    if (this.status === "disposed") return;
    this.coalescer.dispose();
    this.broker.cancelForSession(this.key);
    try {
      await this.query?.interrupt();
    } catch {
      /* ignore */
    }
    try {
      await this.query?.return(undefined);
    } catch {
      /* ignore */
    }
    this.inputQueue.close();
    this.setStatus("disposed");
  }

  // ----------------------------------------------------------------------- //
  // PermissionSessionSink + event log
  // ----------------------------------------------------------------------- //

  logEvent(event: SessionEvent): EventEnvelope {
    const env = this.log.append(event);
    this.updatedAt = env.ts;
    this.broadcast(env);
    return env;
  }

  recomputeStatus(): void {
    if (
      this.status === "disposed" ||
      this.status === "error" ||
      this.status === "completed"
    ) {
      return;
    }
    const pending = this.broker.pendingCount(this.key);
    if (pending > 0) {
      this.setStatus("awaiting_permission");
    } else {
      this.setStatus(this.turnInFlight ? "running" : "idle");
    }
  }

  private setStatus(next: SessionStatus): void {
    if (this.status === next) return;
    this.status = next;
    this.logEvent({ type: "session.status", status: next });
  }

  // ----------------------------------------------------------------------- //
  // Views
  // ----------------------------------------------------------------------- //

  get statusValue(): SessionStatus {
    return this.status;
  }

  get meta(): SessionMeta {
    return {
      sessionKey: this.key,
      sdkSessionId: this.sdkSessionId,
      kind: this.kind,
      profile: this.profile.name,
      cwd: this.cwd,
      title: this.title,
      status: this.status,
      model: this.model,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      lastSeq: this.log.lastSeq,
      costUsd: this.costUsd,
      jobId: this.jobId,
    };
  }

  get eventLog(): EventLog {
    return this.log;
  }

  // ----------------------------------------------------------------------- //
  // SDK options
  // ----------------------------------------------------------------------- //

  private buildOptions(): Options {
    const options: Options = {
      cwd: this.cwd,
      // Load-bearing: without these the session silently loses CLAUDE.md /
      // cortex.md — no routing protocol, no skills. Makes web == terminal.
      settingSources: ["user", "project", "local"],
      systemPrompt: { type: "preset", preset: "claude_code" },
      includePartialMessages: true,
      forwardSubagentText: true,
      allowedTools: this.profile.allowedTools,
      canUseTool: this.broker.makeCanUseTool(this),
      permissionMode: "default",
    };

    if (this.resumeSdkSessionId) {
      options.resume = this.resumeSdkSessionId;
    }

    // A/B init cost: mcp:false boots zero MCP servers. `strictMcpConfig` makes
    // the SDK ignore every other MCP source (project .mcp.json, user settings,
    // plugins, agent frontmatter); combined with an empty `mcpServers` the fleet
    // never spins. (sdk.d.ts: Options.strictMcpConfig, Options.mcpServers.)
    if (!this.mcp) {
      options.mcpServers = {};
      options.strictMcpConfig = true;
    }

    // PreToolUse hooks. The ASK hook is load-bearing: settings-file allow rules
    // (loaded via settingSources) can auto-approve a tool before canUseTool is
    // ever consulted, shadowing our chat gate — the SDK warns about this on
    // stdout. The ask hook forces `ask` for anything the profile doesn't itself
    // auto-approve, so chat Bash always shows a card. The run profile stacks its
    // hard-denylist DENY hook FIRST (deny wins) ahead of the ask hook.
    const preToolUse: HookCallbackMatcher[] = [];
    if (this.profile.denyPatterns.length > 0) {
      preToolUse.push(makeDenyHook(this.profile));
    }
    preToolUse.push(makeAskHook(this.profile, this.cwd));
    options.hooks = { PreToolUse: preToolUse };

    return options;
  }
}

function errorText(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
