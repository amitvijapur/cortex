// Cortex Command — ToolCallCard: collapsible card per tool call.
//
// Spinner while running; border state running / ok / err. Chooses a per-tool
// body (Bash / Diff / Read / generic JSON). When a permission gate is attached
// it renders the PermissionCard inline. Task cards receive their subagent's
// child blocks (already rendered) and show them indented with the agent label.

import { useState, type ReactNode } from "react";
import type { PendingApproval } from "@cortex-command/shared";
import type { AgentInfo, Block } from "../../lib/store";
import { cx } from "../../lib/format";
import { BashCardBody } from "../toolbodies/BashCardBody";
import { DiffCard } from "../toolbodies/DiffCard";
import { ReadCardBody } from "../toolbodies/ReadCardBody";
import { GenericJsonBody } from "../toolbodies/GenericJsonBody";
import { PermissionCard } from "./PermissionCard";

type ToolBlock = Extract<Block, { kind: "tool" }>;

const DIFF_TOOLS = new Set(["edit", "write", "multiedit", "notebookedit"]);

function primaryLine(block: ToolBlock): string {
  const input = block.input;
  if (input && typeof input === "object") {
    const obj = input as Record<string, unknown>;
    if (typeof obj["command"] === "string") return obj["command"] as string;
    if (typeof obj["file_path"] === "string") return obj["file_path"] as string;
    if (typeof obj["description"] === "string") return obj["description"] as string;
    if (typeof obj["pattern"] === "string") return obj["pattern"] as string;
  }
  return "";
}

function Body({ block }: { block: ToolBlock }): ReactNode {
  const tool = block.name.toLowerCase();
  if (tool === "bash") return <BashCardBody input={block.input} result={block.result} />;
  if (DIFF_TOOLS.has(tool)) {
    // Prefer the client diff; if the input isn't diff-shaped yet, show nothing.
    return <DiffCard name={block.name} input={block.input} />;
  }
  if (tool === "read") return <ReadCardBody input={block.input} result={block.result} />;
  return <GenericJsonBody input={block.input} result={block.result} />;
}

export function ToolCallCard({
  block,
  approval,
  agent,
  childrenNode,
}: {
  block: ToolBlock;
  approval?: PendingApproval;
  agent?: AgentInfo;
  childrenNode?: ReactNode;
}): React.ReactNode {
  const isError = block.result?.isError ?? false;
  const running = block.running;
  const pendingApproval = approval?.status === "pending";

  const [open, setOpen] = useState<boolean>(
    () => running || pendingApproval || isError || block.name.toLowerCase() !== "read",
  );

  // A tool blocked on a decision reads as "awaiting", not "running".
  const state = pendingApproval ? "await" : running ? "running" : isError ? "err" : "ok";
  const isTask = block.name.toLowerCase() === "task";

  return (
    <div className={cx("toolcard", "tc-" + state, open && "open")}>
      <button className="toolcard-h" onClick={() => setOpen((o) => !o)}>
        <span className="tc-chev">{open ? "▾" : "▸"}</span>
        {pendingApproval ? (
          <span className="tc-dot tc-dot-await" />
        ) : running ? (
          <span className="tc-spinner" aria-hidden="true" />
        ) : (
          <span className={cx("tc-dot", isError ? "tc-dot-err" : "tc-dot-ok")} />
        )}
        <span className="tc-name mono">{block.name}</span>
        {agent && (
          <span className="tc-agent mono">
            {agent.agentType ?? "agent"}
            {agent.status === "running" ? " · running" : agent.status === "error" ? " · error" : " · done"}
          </span>
        )}
        <span className="tc-primary mono">{primaryLine(block)}</span>
        {pendingApproval ? (
          <span className="tc-status mono tc-status-await">awaiting approval</span>
        ) : (
          running && <span className="tc-status mono">running…</span>
        )}
      </button>

      {open && (
        <div className="toolcard-body">
          {isTask && agent?.description && <div className="tb-desc">{agent.description}</div>}
          <Body block={block} />
          {approval && <PermissionCard approval={approval} />}
          {childrenNode && <div className="subagent-children">{childrenNode}</div>}
        </div>
      )}
    </div>
  );
}
