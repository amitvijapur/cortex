// Cortex Command — SDK message → SessionEvent[] pipeline (pure-ish).
//
// `translate(msg, state)` is the single mapping point from raw Agent-SDK
// messages to the normalized, UI-shaped SessionEvents in the shared contract.
// It performs no I/O and no logging; it only reads `msg` and threads a small
// mutable `TranslateState` so it can dedupe tool.start across partial+full
// deliveries, pair agent.start/stop, and — critically — remap the SDK's
// per-MESSAGE content-block index (which restarts at 0 for every assistant
// message) into a session-monotonic index. The web store keys text/thinking
// blocks by (parentToolUseId, index) "within the turn", so without the remap a
// normal multi-step turn (text → tool → more text) would collide at index 0 and
// the second text block would overwrite the first.
//
// Index invariant (load-bearing): a streaming delta and its authoritative
// `.done` for the same block MUST carry the same emitted index — that is how the
// client pairs them. Both are computed as `currentMessageOffset + sdkIndex`, and
// only the main thread's own full message consumes/clears that offset.
//
// It also owns the truncation policy for tool output (first HEAD + last TAIL
// chars, `truncated` + `fullLength`). Blob spill of the full output is M2 — the
// hook point is marked below; until then `outputRef` is left unset.

import type { SDKMessage } from "@anthropic-ai/claude-agent-sdk";
import type { SessionEvent, TokenUsage } from "@cortex-command/shared";
import type { TurnResultSubtype } from "@cortex-command/shared";
import { OUTPUT_PREVIEW_HEAD, OUTPUT_PREVIEW_TAIL } from "../config.js";

// --------------------------------------------------------------------------- //
// Translate state (threaded per session, owned by Session)
// --------------------------------------------------------------------------- //

export interface TranslateState {
  /** tool_use ids for which a tool.start has already been emitted. */
  startedTools: Set<string>;
  /**
   * Discovered subagents, keyed by the parent Task tool_use id (the indent
   * anchor). Lets us emit agent.start once and pair agent.stop to the Task's
   * tool_result.
   */
  subagents: Map<string, { agentId: string; agentType?: string; description?: string }>;

  // ---- session-monotonic block indexing (keyed by API message.id) -------- //
  //
  // The CLI splits ONE API assistant message (one message.id) into MULTIPLE
  // `assistant` deliveries, e.g. [thinking] then [text], while the partial
  // stream carries continuous API content-block indexes (0, 1, …). Each
  // delivery's content array restarts at position 0, so we must map a delivery's
  // array position `i` to its API index via a running per-message delivered
  // count. Deltas and their authoritative `.done` then share the same emitted
  // index (offset + apiIndex) — the invariant the web store pairs on.
  /** Per API message.id: its global block offset + blocks already delivered. */
  messages: Map<string, { offset: number; delivered: number }>;
  /** message.id whose partials (content_block_*) are currently streaming. */
  currentPartialMsgId: string | null;
  /** Session-global high-water block index (offset for the next new message). */
  nextBlockIndex: number;
}

export function newTranslateState(): TranslateState {
  return {
    startedTools: new Set(),
    subagents: new Map(),
    messages: new Map(),
    currentPartialMsgId: null,
    nextBlockIndex: 0,
  };
}

/** Get (or create) the index window for an API message.id. */
function messageWindow(state: TranslateState, msgId: string): { offset: number; delivered: number } {
  let entry = state.messages.get(msgId);
  if (!entry) {
    entry = { offset: state.nextBlockIndex, delivered: 0 };
    state.messages.set(msgId, entry);
  }
  return entry;
}

/** Raise the session high-water mark to cover an emitted block index. */
function bumpNextIndex(state: TranslateState, blockIndex: number): void {
  if (blockIndex + 1 > state.nextBlockIndex) state.nextBlockIndex = blockIndex + 1;
}

// --------------------------------------------------------------------------- //
// Minimal structural views of the SDK shapes we read
// --------------------------------------------------------------------------- //

type Rec = Record<string, unknown>;
const isRec = (v: unknown): v is Rec => typeof v === "object" && v !== null;
const asStr = (v: unknown): string | undefined => (typeof v === "string" ? v : undefined);
const asNum = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);

// --------------------------------------------------------------------------- //
// Entry point
// --------------------------------------------------------------------------- //

/**
 * Map one SDK message to zero or more SessionEvents. The `system/init` message
 * is intentionally NOT handled here — Session captures session_id/model/status
 * from it directly (a side effect) before deciding whether to translate.
 */
export function translate(msg: SDKMessage, state: TranslateState): SessionEvent[] {
  switch (msg.type) {
    case "stream_event":
      return fromPartial(msg as unknown as PartialLike, state);
    case "assistant":
      return fromAssistant(msg as unknown as AssistantLike, state);
    case "user":
      return fromUser(msg as unknown as UserLike, state);
    case "result":
      return fromResult(msg as unknown as ResultLike);
    default:
      return [];
  }
}

// --------------------------------------------------------------------------- //
// Partial (streaming) messages → coalesced deltas + early tool.start
// --------------------------------------------------------------------------- //

interface PartialLike {
  type: "stream_event";
  event: Rec;
  parent_tool_use_id: string | null;
}

/**
 * Offset for the message whose partials are currently streaming. Falls back to
 * the high-water mark if no message_start has been seen (defensive; the real CLI
 * always precedes content blocks with a message_start carrying the id).
 */
function partialOffset(state: TranslateState): number {
  const id = state.currentPartialMsgId;
  if (id) {
    const entry = state.messages.get(id);
    if (entry) return entry.offset;
  }
  return state.nextBlockIndex;
}

function fromPartial(msg: PartialLike, state: TranslateState): SessionEvent[] {
  const parent = msg.parent_tool_use_id ?? null;
  const event = msg.event;
  const etype = asStr(event["type"]);
  const sdkIndex = asNum(event["index"]) ?? 0;

  if (etype === "message_start") {
    // One message_start per API message (NOT per split delivery). Anchor this
    // message.id's block offset above everything emitted so far and remember it
    // so this message's content_block_* events resolve to the same window.
    const messageObj = isRec(event["message"]) ? event["message"] : undefined;
    const msgId = messageObj ? asStr(messageObj["id"]) : undefined;
    if (msgId) {
      messageWindow(state, msgId);
      state.currentPartialMsgId = msgId;
    }
    return [];
  }

  if (etype === "content_block_start") {
    const index = partialOffset(state) + sdkIndex;
    bumpNextIndex(state, index);
    const block = isRec(event["content_block"]) ? event["content_block"] : undefined;
    if (block && asStr(block["type"]) === "tool_use") {
      const id = asStr(block["id"]);
      const name = asStr(block["name"]);
      if (id && name) {
        // Record here so the full assistant message dedupes and does NOT emit a
        // second tool.start for the same toolUseId.
        state.startedTools.add(id);
        return [{ type: "tool.start", toolUseId: id, name, index, parentToolUseId: parent }];
      }
    }
    return [];
  }

  if (etype === "content_block_delta") {
    const index = partialOffset(state) + sdkIndex;
    bumpNextIndex(state, index);
    const delta = isRec(event["delta"]) ? event["delta"] : undefined;
    if (!delta) return [];
    const dtype = asStr(delta["type"]);
    if (dtype === "text_delta") {
      const text = asStr(delta["text"]);
      if (text) return [{ type: "text.delta", text, index, parentToolUseId: parent }];
    } else if (dtype === "thinking_delta") {
      const text = asStr(delta["thinking"]);
      if (text) return [{ type: "thinking.delta", text, index, parentToolUseId: parent }];
    }
    // input_json_delta / signature_delta: tool input arrives whole with the
    // full assistant message; signatures are not surfaced.
    return [];
  }

  if (etype === "content_block_stop") {
    bumpNextIndex(state, partialOffset(state) + sdkIndex);
    return [];
  }

  // message_delta / message_stop: no event, no index change.
  return [];
}

// --------------------------------------------------------------------------- //
// Full assistant message → authoritative text.done / thinking.done, tool.input,
// tool.start (dedup), and agent.start enrichment for subagents.
// --------------------------------------------------------------------------- //

interface AssistantLike {
  type: "assistant";
  message: { content?: unknown; id?: string };
  parent_tool_use_id: string | null;
  subagent_type?: string;
  task_description?: string;
}

function fromAssistant(msg: AssistantLike, state: TranslateState): SessionEvent[] {
  const out: SessionEvent[] = [];
  const parent = msg.parent_tool_use_id ?? null;

  // Subagent enrichment: the first assistant message under a Task carries the
  // subagent_type + task_description — better labels than the SubagentStart
  // hook alone. Emit agent.start once, keyed by the parent Task tool_use id.
  if (parent && msg.subagent_type && !state.subagents.has(parent)) {
    state.subagents.set(parent, {
      agentId: parent,
      agentType: msg.subagent_type,
      description: msg.task_description,
    });
    out.push({
      type: "agent.start",
      agentId: parent,
      parentToolUseId: parent,
      agentType: msg.subagent_type,
      description: msg.task_description,
    });
  }

  const content = Array.isArray(msg.message?.content) ? (msg.message.content as unknown[]) : [];

  // Resolve this delivery's window by message.id. Because ONE API message may be
  // split into several deliveries, a delivery's blocks are the NEXT `delivered`
  // API indexes: block at array position i → API index `delivered + i`, emitted
  // at `offset + delivered + i` — the same value its streamed deltas used. A
  // delivery with no message.id (e.g. never-streamed subagent forward) takes a
  // fresh window at the high-water mark.
  const msgId = asStr(msg.message?.id);
  const window = msgId ? messageWindow(state, msgId) : { offset: state.nextBlockIndex, delivered: 0 };
  const base = window.offset + window.delivered;

  content.forEach((raw, i) => {
    if (!isRec(raw)) return;
    const index = base + i;
    const btype = asStr(raw["type"]);
    if (btype === "text") {
      const text = asStr(raw["text"]) ?? "";
      out.push({ type: "text.done", text, index, parentToolUseId: parent });
    } else if (btype === "thinking") {
      const text = asStr(raw["thinking"]) ?? "";
      out.push({ type: "thinking.done", text, index, parentToolUseId: parent });
    } else if (btype === "tool_use") {
      const id = asStr(raw["id"]);
      const name = asStr(raw["name"]);
      if (!id || !name) return;
      if (!state.startedTools.has(id)) {
        state.startedTools.add(id);
        out.push({ type: "tool.start", toolUseId: id, name, index, parentToolUseId: parent });
      }
      out.push({
        type: "tool.input",
        toolUseId: id,
        name,
        input: raw["input"],
        index,
        parentToolUseId: parent,
      });
    }
  });

  // Count these blocks as delivered for this message.id and advance the mark.
  window.delivered += content.length;
  state.nextBlockIndex = Math.max(state.nextBlockIndex, window.offset + window.delivered);

  return out;
}

// --------------------------------------------------------------------------- //
// User message (tool_result carrier) → tool.result (+ agent.stop pairing)
// --------------------------------------------------------------------------- //

interface UserLike {
  type: "user";
  message: { content?: unknown };
  parent_tool_use_id: string | null;
  tool_use_result?: unknown;
}

function fromUser(msg: UserLike, state: TranslateState): SessionEvent[] {
  const content = msg.message?.content;
  if (!Array.isArray(content)) return []; // plain user text is our own echo — ignore

  const out: SessionEvent[] = [];
  const structuredPatch = extractStructuredPatch(msg.tool_use_result);

  for (const raw of content) {
    if (!isRec(raw) || asStr(raw["type"]) !== "tool_result") continue;
    const toolUseId = asStr(raw["tool_use_id"]);
    if (!toolUseId) continue;
    const isError = raw["is_error"] === true;
    const full = contentToString(raw["content"]);
    const { preview, truncated, fullLength } = truncateOutput(full);

    // A completed Task tool_result closes its subagent — pair agent.stop.
    const sub = state.subagents.get(toolUseId);
    if (sub) {
      state.subagents.delete(toolUseId);
      out.push({
        type: "agent.stop",
        agentId: sub.agentId,
        parentToolUseId: toolUseId,
        status: isError ? "error" : "completed",
      });
    }

    out.push({
      type: "tool.result",
      toolUseId,
      isError,
      preview,
      truncated,
      fullLength,
      // M2 blob-spill hook point: when `truncated`, spill `full` to a blob and
      // set `outputRef` to its REST path. Left unset in M1.
      ...(structuredPatch !== undefined ? { structuredPatch } : {}),
      parentToolUseId: msg.parent_tool_use_id ?? null,
    });
  }

  return out;
}

// --------------------------------------------------------------------------- //
// Result message → turn.result
// --------------------------------------------------------------------------- //

interface ResultLike {
  type: "result";
  subtype: string;
  is_error?: boolean;
  total_cost_usd?: number;
  duration_ms?: number;
  num_turns?: number;
  result?: string;
  usage?: unknown;
  errors?: unknown;
}

const RESULT_SUBTYPES: ReadonlySet<TurnResultSubtype> = new Set<TurnResultSubtype>([
  "success",
  "error_during_execution",
  "error_max_turns",
  "error_max_budget_usd",
  "error_max_structured_output_retries",
]);

function fromResult(msg: ResultLike): SessionEvent[] {
  const subtype: TurnResultSubtype = RESULT_SUBTYPES.has(msg.subtype as TurnResultSubtype)
    ? (msg.subtype as TurnResultSubtype)
    : "error_during_execution";
  const isError = subtype !== "success" || msg.is_error === true;
  const errors = Array.isArray(msg.errors)
    ? msg.errors.filter((e): e is string => typeof e === "string")
    : undefined;

  return [
    {
      type: "turn.result",
      subtype,
      isError,
      costUsd: msg.total_cost_usd ?? 0,
      durationMs: msg.duration_ms ?? 0,
      numTurns: msg.num_turns ?? 0,
      ...(subtype === "success" && typeof msg.result === "string"
        ? { resultText: msg.result }
        : {}),
      ...(msg.usage ? { usage: pickUsage(msg.usage) } : {}),
      ...(errors && errors.length ? { errors } : {}),
    },
  ];
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

export function truncateOutput(
  full: string,
  head: number = OUTPUT_PREVIEW_HEAD,
  tail: number = OUTPUT_PREVIEW_TAIL,
): { preview: string; truncated: boolean; fullLength: number } {
  const fullLength = full.length;
  if (fullLength <= head + tail) {
    return { preview: full, truncated: false, fullLength };
  }
  const omitted = fullLength - head - tail;
  const preview = `${full.slice(0, head)}\n… [truncated ${omitted} chars] …\n${full.slice(-tail)}`;
  return { preview, truncated: true, fullLength };
}

function contentToString(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((b) => {
        if (typeof b === "string") return b;
        if (isRec(b) && asStr(b["type"]) === "text") return asStr(b["text"]) ?? "";
        return JSON.stringify(b);
      })
      .join("");
  }
  if (content == null) return "";
  return JSON.stringify(content);
}

function extractStructuredPatch(toolUseResult: unknown): unknown {
  if (isRec(toolUseResult) && "structuredPatch" in toolUseResult) {
    return toolUseResult["structuredPatch"];
  }
  return undefined;
}

function pickUsage(usage: unknown): TokenUsage {
  const u = isRec(usage) ? usage : {};
  const out: TokenUsage = {};
  const input = asNum(u["input_tokens"]);
  const output = asNum(u["output_tokens"]);
  const cacheCreate = asNum(u["cache_creation_input_tokens"]);
  const cacheRead = asNum(u["cache_read_input_tokens"]);
  if (input !== undefined) out.input_tokens = input;
  if (output !== undefined) out.output_tokens = output;
  if (cacheCreate !== undefined) out.cache_creation_input_tokens = cacheCreate;
  if (cacheRead !== undefined) out.cache_read_input_tokens = cacheRead;
  return out;
}
