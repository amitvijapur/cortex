// Cortex Command — routing chip grammar as TSX.
//
// Ported from bin/cortex-ui agentChips()/chipChain() (lines ~535–552). The
// observatory built HTML strings; here we build React nodes from the already
// parsed RoutingLine (system / pattern / parallel[] / reconciler / tier), and
// fall back to splitting the raw `agent` segment on the ∥ / → grammar when the
// structured legs are absent.

import type { ReactNode } from "react";
import type { RoutingLine } from "@cortex-command/shared";

/** Split an agent segment on the chip grammar (∥ parallel legs, → reconciler). */
function splitAgent(agent: string): { legs: string[]; reconciler: string | null } {
  let recon: string | null = null;
  let left = agent;
  const arrow = agent.indexOf("→");
  if (arrow >= 0) {
    left = agent.slice(0, arrow);
    recon = agent.slice(arrow + 1).trim() || null;
  }
  const legs = left
    .split("∥")
    .map((s) => s.trim())
    .filter(Boolean);
  return { legs, reconciler: recon };
}

/** Render the agent chips: parallel legs joined by ∥, then → reconciler. */
export function AgentChips({ routing }: { routing: RoutingLine }): ReactNode {
  let legs = routing.parallel;
  let reconciler = routing.reconciler;
  if ((!legs || legs.length === 0) && routing.agent) {
    const parsed = splitAgent(routing.agent);
    legs = parsed.legs;
    reconciler = reconciler ?? parsed.reconciler;
  }
  if (!legs || legs.length === 0) {
    // Single agent with no parallel structure — render the raw segment as one chip.
    if (!routing.agent) return null;
    return <span className="chip chip-agent">{routing.agent}</span>;
  }
  return (
    <>
      {legs.map((leg, i) => (
        <span key={"leg" + i} style={{ display: "inline-flex", alignItems: "center" }}>
          {i > 0 && <span className="glyph">∥</span>}
          <span className="chip chip-agent">{leg}</span>
        </span>
      ))}
      {reconciler && (
        <>
          <span className="glyph arrow">→</span>
          <span className="chip chip-recon">{reconciler}</span>
        </>
      )}
    </>
  );
}

/** Full chip chain: system › pattern › agents › tier, with › separators. */
export function ChipChain({ routing }: { routing: RoutingLine }): ReactNode {
  const tier = routing.tier;
  const hasAgent =
    (routing.parallel && routing.parallel.length > 0) || Boolean(routing.agent);
  return (
    <div className="chipline">
      {routing.system && <span className="chip chip-sys">{routing.system}</span>}
      {routing.pattern && (
        <>
          <span className="sep">›</span>
          <span className="chip chip-pat">{routing.pattern}</span>
        </>
      )}
      {hasAgent && (
        <>
          <span className="sep">›</span>
          <AgentChips routing={routing} />
        </>
      )}
      {tier && (
        <>
          <span className="sep">›</span>
          <span className={"chip tier tier-" + tier}>{tier}</span>
        </>
      )}
    </div>
  );
}
