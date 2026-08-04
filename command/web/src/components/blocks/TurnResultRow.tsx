// Cortex Command — hairline mono row summarising a completed turn/result.

import { fmtCost, fmtDuration } from "../../lib/format";
import type { TurnResultSubtype } from "@cortex-command/shared";

export function TurnResultRow({
  subtype,
  isError,
  costUsd,
  durationMs,
  numTurns,
}: {
  subtype: TurnResultSubtype;
  isError: boolean;
  costUsd: number;
  durationMs: number;
  numTurns: number;
}): React.ReactNode {
  return (
    <div className={"result-row mono" + (isError ? " err" : "")}>
      <span className="rr-mark">{isError ? "✕" : "✓"}</span>
      <span className="rr-seg">{isError ? subtype : "turn complete"}</span>
      <span className="rr-dot">·</span>
      <span className="rr-seg">{fmtCost(costUsd)}</span>
      <span className="rr-dot">·</span>
      <span className="rr-seg">{numTurns} turns</span>
      <span className="rr-dot">·</span>
      <span className="rr-seg">{fmtDuration(durationMs)}</span>
    </div>
  );
}
