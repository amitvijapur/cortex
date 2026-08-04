// Cortex Command — Transcript: renders the folded block list.
//
// Blocks are a flat, ordered, deterministic fold (store.ts). Here we present
// them: subagent-tagged blocks (parentToolUseId set) are nested under their
// spawning Task ToolCallCard; everything else renders top-level in seq order.

import type { ReactNode } from "react";
import type { PendingApproval } from "@cortex-command/shared";
import type { AgentInfo, Block, SessionState } from "../lib/store";
import { UserTurn } from "./blocks/UserTurn";
import { AssistantText } from "./blocks/AssistantText";
import { ThinkingBlock } from "./blocks/ThinkingBlock";
import { ToolCallCard } from "./blocks/ToolCallCard";
import { RoutingCard } from "./blocks/RoutingCard";
import { TurnResultRow } from "./blocks/TurnResultRow";

interface Ctx {
  approvals: Record<string, PendingApproval>;
  agents: Record<string, AgentInfo>;
  childrenByParent: Map<string, Block[]>;
  toolIds: Set<string>;
}

function renderBlock(block: Block, ctx: Ctx): ReactNode {
  switch (block.kind) {
    case "user":
      return <UserTurn key={block.id} text={block.text} />;
    case "text":
      // Blank, streaming, not-yet-started blocks add noise; skip truly empty ones.
      if (block.text === "" && !block.done) return null;
      return <AssistantText key={block.id} text={block.text} done={block.done} />;
    case "thinking":
      if (block.text === "" && !block.done) return null;
      return <ThinkingBlock key={block.id} text={block.text} done={block.done} />;
    case "routing":
      return <RoutingCard key={block.id} routing={block.routing} />;
    case "turnresult":
      return (
        <TurnResultRow
          key={block.id}
          subtype={block.subtype}
          isError={block.isError}
          costUsd={block.costUsd}
          durationMs={block.durationMs}
          numTurns={block.numTurns}
        />
      );
    case "tool": {
      const approval = block.approvalId ? ctx.approvals[block.approvalId] : undefined;
      const agent = ctx.agents[block.toolUseId];
      const kids = ctx.childrenByParent.get(block.toolUseId);
      const childrenNode =
        kids && kids.length > 0 ? kids.map((k) => renderBlock(k, ctx)) : undefined;
      return (
        <ToolCallCard
          key={block.id}
          block={block}
          approval={approval}
          agent={agent}
          childrenNode={childrenNode}
        />
      );
    }
    default:
      return null;
  }
}

export function Transcript({ session }: { session: SessionState }): React.ReactNode {
  const { blocks, approvals, agents } = session;

  const toolIds = new Set<string>();
  for (const b of blocks) if (b.kind === "tool") toolIds.add(b.toolUseId);

  const childrenByParent = new Map<string, Block[]>();
  for (const b of blocks) {
    const parent = b.parentToolUseId;
    if (parent && toolIds.has(parent)) {
      const arr = childrenByParent.get(parent) ?? [];
      arr.push(b);
      childrenByParent.set(parent, arr);
    }
  }

  const ctx: Ctx = { approvals, agents, childrenByParent, toolIds };

  const topLevel = blocks.filter(
    (b) => !(b.parentToolUseId && toolIds.has(b.parentToolUseId)),
  );

  if (topLevel.length === 0) {
    const booting = session.status === "starting";
    return (
      <div className="transcript-empty mono">
        {booting
          ? "Session is booting — send your first message to begin."
          : "Waiting for the first turn…"}
      </div>
    );
  }

  return <div className="transcript">{topLevel.map((b) => renderBlock(b, ctx))}</div>;
}
