// Cortex Command — delta coalescer.
//
// Text/thinking deltas arrive at token cadence (dozens per second). Appending
// each to the EventLog would blow the ring buffer and flood every WS client, so
// they are buffered here and flushed as a single larger delta when a per-block
// buffer reaches COALESCE_MAX_CHARS or COALESCE_WINDOW_MS elapses — whichever
// first. The authoritative `text.done` (emitted from the full assistant message)
// heals any coalescing loss, so the caller MUST `flushAll()` before appending
// any non-delta event to preserve ordering (a delta must never land after its
// block's done).

import type {
  SessionEvent,
  TextDeltaEvent,
  ThinkingDeltaEvent,
} from "@cortex-command/shared";
import { COALESCE_MAX_CHARS, COALESCE_WINDOW_MS } from "../config.js";

type DeltaKind = "text" | "thinking";

interface Buffer {
  kind: DeltaKind;
  index: number;
  parentToolUseId: string | null;
  text: string;
  timer: ReturnType<typeof setTimeout> | null;
}

export class Coalescer {
  // Insertion-ordered so flushAll emits in the order blocks first appeared.
  private buffers = new Map<string, Buffer>();

  constructor(
    private readonly emit: (event: SessionEvent) => void,
    private readonly windowMs: number = COALESCE_WINDOW_MS,
    private readonly maxChars: number = COALESCE_MAX_CHARS,
  ) {}

  push(event: TextDeltaEvent | ThinkingDeltaEvent): void {
    const kind: DeltaKind = event.type === "text.delta" ? "text" : "thinking";
    const parent = event.parentToolUseId ?? null;
    const key = `${kind}:${parent ?? ""}:${event.index}`;
    let buf = this.buffers.get(key);
    if (!buf) {
      buf = { kind, index: event.index, parentToolUseId: parent, text: "", timer: null };
      this.buffers.set(key, buf);
    }
    buf.text += event.text;
    if (buf.text.length >= this.maxChars) {
      this.flushKey(key);
      return;
    }
    if (!buf.timer) {
      buf.timer = setTimeout(() => this.flushKey(key), this.windowMs);
    }
  }

  private flushKey(key: string): void {
    const buf = this.buffers.get(key);
    if (!buf) return;
    if (buf.timer) clearTimeout(buf.timer);
    this.buffers.delete(key);
    if (buf.text.length === 0) return;
    if (buf.kind === "text") {
      this.emit({
        type: "text.delta",
        text: buf.text,
        index: buf.index,
        parentToolUseId: buf.parentToolUseId,
      });
    } else {
      this.emit({
        type: "thinking.delta",
        text: buf.text,
        index: buf.index,
        parentToolUseId: buf.parentToolUseId,
      });
    }
  }

  /** Emit every buffered delta now (order-preserving). Call before non-deltas. */
  flushAll(): void {
    for (const key of [...this.buffers.keys()]) this.flushKey(key);
  }

  /** Drop all timers/buffers without emitting (session dispose). */
  dispose(): void {
    for (const buf of this.buffers.values()) {
      if (buf.timer) clearTimeout(buf.timer);
    }
    this.buffers.clear();
  }
}
