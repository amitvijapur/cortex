// Cortex Command — server constants (M1).
//
// All tunables in one place so the pipeline, ring buffer, coalescer, permission
// timeouts, and WS backpressure thresholds are auditable from a single file.

export const SERVER_VERSION = "0.1.0-m1";
export const HOST = "127.0.0.1";
export const DEFAULT_PORT = 7788; // observatory keeps 7777
export const OBSERVATORY_PORT = 7777;

/** Only one live chat session at a time (multi-session is M3, UI-only). */
export const MAX_CHAT_SESSIONS = 1;

/** EventLog ring buffer caps (per session). */
export const EVENTLOG_MAX_EVENTS = 5_000;
export const EVENTLOG_MAX_BYTES = 8 * 1024 * 1024;

/** Delta coalescing: flush a text/thinking buffer at whichever fires first. */
export const COALESCE_WINDOW_MS = 30;
export const COALESCE_MAX_CHARS = 512;

/** Absolute default-deny windows for a pending approval. */
export const CHAT_APPROVAL_TIMEOUT_MS = 10 * 60 * 1000;
export const RUN_APPROVAL_TIMEOUT_MS = 60 * 1000;

/** tool.result output truncation (first HEAD + last TAIL chars kept). */
export const OUTPUT_PREVIEW_HEAD = 4_000;
export const OUTPUT_PREVIEW_TAIL = 2_000;

/** Per-client WS backpressure: above this, skip delta frames (text.done heals). */
export const WS_MAX_BUFFERED_BYTES = 1024 * 1024;

/** ws-level heartbeat cadence. */
export const WS_HEARTBEAT_MS = 30_000;

/**
 * The message returned to the model when an approval default-denies on timeout.
 * Rendered from the profile's timeout so chat (10 min) and run (60 s) both read
 * naturally; the chat form matches the plan's wording verbatim.
 */
export function timeoutDenyMessage(timeoutMs: number): string {
  const mins = Math.round(timeoutMs / 60_000);
  const label =
    mins >= 1
      ? `${mins} minute${mins > 1 ? "s" : ""}`
      : `${Math.max(1, Math.round(timeoutMs / 1000))} seconds`;
  return `Auto-denied: no operator decision within ${label}. Ask again if still needed.`;
}
