// Cortex Command — RoutingCard: renders a detected Cortex routing line using the
// observatory chip grammar (system › pattern › agents › tier), plus the raw
// tag block when present.

import type { RoutingLine } from "@cortex-command/shared";
import { ChipChain } from "../../lib/routing";

export function RoutingCard({ routing }: { routing: RoutingLine }): React.ReactNode {
  return (
    <div className="routing-card">
      <div className="routing-badge mono">ROUTE</div>
      <div className="routing-main">
        <ChipChain routing={routing} />
        {routing.tags && <div className="routing-tags mono">[{routing.tags}]</div>}
      </div>
    </div>
  );
}
