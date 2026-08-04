// Cortex Command — client-side line diff (hand-rolled LCS, no library).
//
// Diffs are computed in the browser from a tool's INPUT: Edit/MultiEdit
// (old_string → new_string) and Write (content, against an empty original).
// The server may also ship a `structuredPatch`; when present the DiffCard
// prefers it, but this module is the fallback that always works.

export type DiffKind = "ctx" | "add" | "del";

export interface DiffLine {
  kind: DiffKind;
  text: string;
}

/** One contiguous change region for the Edit/MultiEdit view. */
export interface DiffHunk {
  /** Optional label (MultiEdit numbers its edits). */
  label?: string;
  lines: DiffLine[];
  added: number;
  removed: number;
}

const MAX_DIFF_LINES = 1200; // guardrail against O(n·m) blowups on huge inputs

function splitLines(s: string): string[] {
  if (s === "") return [];
  // Keep it simple + deterministic: normalise CRLF, split on \n.
  return s.replace(/\r\n/g, "\n").split("\n");
}

/**
 * Classic LCS line diff. Returns an interleaved del/add/ctx sequence.
 * Falls back to a whole-block replace when either side is very large.
 */
export function lineDiff(oldStr: string, newStr: string): DiffLine[] {
  const a = splitLines(oldStr);
  const b = splitLines(newStr);

  if (a.length === 0 && b.length === 0) return [];
  if (a.length > MAX_DIFF_LINES || b.length > MAX_DIFF_LINES) {
    return [
      ...a.map((t): DiffLine => ({ kind: "del", text: t })),
      ...b.map((t): DiffLine => ({ kind: "add", text: t })),
    ];
  }

  const n = a.length;
  const m = b.length;
  // dp[i][j] = LCS length of a[i:] and b[j:]
  const dp: number[][] = Array.from({ length: n + 1 }, () =>
    new Array<number>(m + 1).fill(0),
  );
  for (let i = n - 1; i >= 0; i--) {
    const rowI = dp[i]!;
    const rowI1 = dp[i + 1]!;
    for (let j = m - 1; j >= 0; j--) {
      if (a[i] === b[j]) rowI[j] = rowI1[j + 1]! + 1;
      else rowI[j] = Math.max(rowI1[j]!, rowI[j + 1]!);
    }
  }

  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ kind: "ctx", text: a[i]! });
      i++;
      j++;
    } else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) {
      out.push({ kind: "del", text: a[i]! });
      i++;
    } else {
      out.push({ kind: "add", text: b[j]! });
      j++;
    }
  }
  while (i < n) out.push({ kind: "del", text: a[i++]! });
  while (j < m) out.push({ kind: "add", text: b[j++]! });
  return out;
}

function tally(lines: DiffLine[]): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const l of lines) {
    if (l.kind === "add") added++;
    else if (l.kind === "del") removed++;
  }
  return { added, removed };
}

/** A single Edit/Write becomes one hunk. */
export function hunkFromReplace(oldStr: string, newStr: string, label?: string): DiffHunk {
  const lines = lineDiff(oldStr, newStr);
  const { added, removed } = tally(lines);
  return { label, lines, added, removed };
}

/** Shape of a MultiEdit edit entry. */
interface MultiEditEntry {
  old_string?: unknown;
  new_string?: unknown;
}

/**
 * Derive the diff hunks + target path from a tool's input, for Edit / Write /
 * MultiEdit / NotebookEdit. Returns null when the tool isn't diff-shaped.
 */
export function diffFromToolInput(
  name: string,
  input: unknown,
): { path: string | null; hunks: DiffHunk[] } | null {
  if (input == null || typeof input !== "object") return null;
  const obj = input as Record<string, unknown>;
  const path =
    typeof obj["file_path"] === "string"
      ? (obj["file_path"] as string)
      : typeof obj["path"] === "string"
        ? (obj["path"] as string)
        : typeof obj["notebook_path"] === "string"
          ? (obj["notebook_path"] as string)
          : null;

  const tool = name.toLowerCase();

  if (tool === "write") {
    const content = typeof obj["content"] === "string" ? (obj["content"] as string) : "";
    return { path, hunks: [hunkFromReplace("", content)] };
  }

  if (tool === "edit" || tool === "notebookedit") {
    const oldS =
      typeof obj["old_string"] === "string"
        ? (obj["old_string"] as string)
        : typeof obj["old_source"] === "string"
          ? (obj["old_source"] as string)
          : "";
    const newS =
      typeof obj["new_string"] === "string"
        ? (obj["new_string"] as string)
        : typeof obj["new_source"] === "string"
          ? (obj["new_source"] as string)
          : "";
    return { path, hunks: [hunkFromReplace(oldS, newS)] };
  }

  if (tool === "multiedit") {
    const edits = Array.isArray(obj["edits"]) ? (obj["edits"] as MultiEditEntry[]) : [];
    const hunks = edits.map((e, idx) => {
      const oldS = typeof e.old_string === "string" ? e.old_string : "";
      const newS = typeof e.new_string === "string" ? e.new_string : "";
      return hunkFromReplace(oldS, newS, "edit " + (idx + 1));
    });
    return { path, hunks };
  }

  return null;
}
