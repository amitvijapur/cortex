// Cortex Command — small formatting + class-name helpers.
// No dependencies; pure functions so components stay declarative.

/** Join truthy class names. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Cost in USD, mono-friendly, always 4 decimals ($0.0000). */
export function fmtCost(n: number): string {
  const v = Number.isFinite(n) ? n : 0;
  return "$" + v.toFixed(4);
}

/** Compact duration: "820ms", "1.4s", "3m 04s". */
export function fmtDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return Math.round(ms) + "ms";
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + "s";
  const m = Math.floor(s / 60);
  const rem = Math.floor(s % 60);
  return m + "m " + String(rem).padStart(2, "0") + "s";
}

/** Wall-clock HH:MM (24h, local). */
export function fmtClock(epochMs: number): string {
  if (!Number.isFinite(epochMs)) return "--:--";
  const d = new Date(epochMs);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return hh + ":" + mm;
}

/** Relative "ago" string for a past epoch-ms timestamp. */
export function ago(epochMs: number): string {
  if (!Number.isFinite(epochMs)) return "";
  let s = Math.max(0, (Date.now() - epochMs) / 1000);
  if (s < 60) return Math.floor(s) + "s ago";
  const m = s / 60;
  if (m < 60) return Math.floor(m) + "m ago";
  const h = m / 60;
  if (h < 24) return Math.floor(h) + "h ago";
  const d = h / 24;
  if (d < 30) return Math.floor(d) + "d ago";
  const mo = d / 30;
  if (mo < 12) return Math.floor(mo) + "mo ago";
  return Math.floor(d / 365) + "y ago";
}

/** Keep the tail of a long id, e.g. sdk session ids. */
export function truncId(id: string | null | undefined, keep = 12): string {
  if (!id) return "—";
  if (id.length <= keep) return id;
  return "…" + id.slice(-keep);
}

/** Collapse a cwd to a short, readable form (last 2 path segments). */
export function shortCwd(cwd: string): string {
  if (!cwd) return "—";
  const parts = cwd.split("/").filter(Boolean);
  if (parts.length <= 2) return cwd;
  return ".../" + parts.slice(-2).join("/");
}

/** mm:ss countdown from a remaining-ms value (clamped at 0). */
export function fmtCountdown(remainingMs: number): string {
  const s = Math.max(0, Math.ceil(remainingMs / 1000));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m + ":" + String(rem).padStart(2, "0");
}
