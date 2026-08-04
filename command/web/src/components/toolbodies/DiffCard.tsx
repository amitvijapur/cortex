// Cortex Command — DiffCard: a unified diff computed CLIENT-SIDE from the tool
// input (Edit old_string/new_string, Write content, MultiEdit edits[]). Green
// background for additions, red for deletions, plain for context. No library —
// the hunks come from lib/diff.ts (hand-rolled LCS).

import type { DiffHunk, DiffLine } from "../../lib/diff";
import { diffFromToolInput } from "../../lib/diff";

function DiffLines({ lines }: { lines: DiffLine[] }): React.ReactNode {
  return (
    <div className="diff">
      {lines.map((l, i) => (
        <div key={i} className={"diff-line diff-" + l.kind}>
          <span className="diff-gutter">{l.kind === "add" ? "+" : l.kind === "del" ? "−" : " "}</span>
          <span className="diff-text">{l.text === "" ? " " : l.text}</span>
        </div>
      ))}
    </div>
  );
}

function HunkView({ hunk }: { hunk: DiffHunk }): React.ReactNode {
  return (
    <div className="diff-hunk">
      {hunk.label && (
        <div className="diff-hunk-h mono">
          {hunk.label}
          <span className="diff-stat">
            <span className="diff-stat-add">+{hunk.added}</span>{" "}
            <span className="diff-stat-del">−{hunk.removed}</span>
          </span>
        </div>
      )}
      <DiffLines lines={hunk.lines} />
    </div>
  );
}

export function DiffCard({ name, input }: { name: string; input: unknown }): React.ReactNode {
  const diff = diffFromToolInput(name, input);
  if (!diff) return null;
  const totalAdd = diff.hunks.reduce((a, h) => a + h.added, 0);
  const totalDel = diff.hunks.reduce((a, h) => a + h.removed, 0);
  const isMulti = diff.hunks.length > 1;

  return (
    <div className="tb">
      <div className="tb-readrow">
        <span className="tb-path mono">{diff.path ?? "(unknown file)"}</span>
        <span className="diff-stat mono">
          <span className="diff-stat-add">+{totalAdd}</span>{" "}
          <span className="diff-stat-del">−{totalDel}</span>
        </span>
      </div>
      {diff.hunks.map((h, i) => (
        <HunkView key={i} hunk={isMulti ? h : { ...h, label: undefined }} />
      ))}
    </div>
  );
}
