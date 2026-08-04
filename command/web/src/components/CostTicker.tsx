// Cortex Command — cumulative cost readout (mono, tabular-nums).

import { fmtCost } from "../lib/format";

export function CostTicker({ cost }: { cost: number }): React.ReactNode {
  return (
    <span className="cost-ticker mono" title="Cumulative session cost">
      <span className="cost-k">COST</span>
      <span className="cost-v">{fmtCost(cost)}</span>
    </span>
  );
}
