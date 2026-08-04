// Cortex Command — per-session append-only EventLog with a bounded ring buffer.
//
// Every session event is appended here with a monotonic `seq`, then broadcast.
// The buffer is capped by event count AND byte size; when it evicts the oldest
// entries it remembers the highest dropped seq so `replay(sinceSeq)` can report
// a truncated gap (the client then knows its fold is not from the true start).

import type { EventEnvelope, SessionEvent } from "@cortex-command/shared";
import { EVENTLOG_MAX_BYTES, EVENTLOG_MAX_EVENTS } from "../config.js";

interface Entry {
  env: EventEnvelope;
  size: number;
}

export interface ReplaySlice {
  events: EventEnvelope[];
  /** First replayed seq (or `sinceSeq` when the slice is empty). */
  fromSeq: number;
  /** Last replayed seq (or the log's lastSeq when the slice is empty). */
  toSeq: number;
  count: number;
  /** True when events with seq > sinceSeq were evicted before this replay. */
  truncated: boolean;
}

export class EventLog {
  private entries: Entry[] = [];
  private seqCounter = 0;
  private bytes = 0;
  /** Highest seq evicted from the ring (0 = nothing dropped yet). */
  private droppedThrough = 0;

  constructor(
    private readonly sessionKey: string,
    private readonly maxEvents: number = EVENTLOG_MAX_EVENTS,
    private readonly maxBytes: number = EVENTLOG_MAX_BYTES,
  ) {}

  get lastSeq(): number {
    return this.seqCounter;
  }

  append(event: SessionEvent, ts: number = Date.now()): EventEnvelope {
    const seq = ++this.seqCounter;
    const env: EventEnvelope = {
      type: "event",
      sessionKey: this.sessionKey,
      seq,
      ts,
      event,
    };
    const size = estimateSize(env);
    this.entries.push({ env, size });
    this.bytes += size;
    this.evict();
    return env;
  }

  private evict(): void {
    while (
      this.entries.length > this.maxEvents ||
      (this.bytes > this.maxBytes && this.entries.length > 1)
    ) {
      const dropped = this.entries.shift();
      if (!dropped) break;
      this.bytes -= dropped.size;
      this.droppedThrough = dropped.env.seq;
    }
  }

  replay(sinceSeq: number): ReplaySlice {
    const events: EventEnvelope[] = [];
    for (const e of this.entries) {
      if (e.env.seq > sinceSeq) events.push(e.env);
    }
    const truncated = sinceSeq < this.droppedThrough;
    const first = events[0];
    const last = events[events.length - 1];
    return {
      events,
      fromSeq: first ? first.seq : sinceSeq,
      toSeq: last ? last.seq : this.seqCounter,
      count: events.length,
      truncated,
    };
  }
}

function estimateSize(env: EventEnvelope): number {
  // Cheap, deterministic proxy for wire/memory footprint.
  return JSON.stringify(env).length;
}
