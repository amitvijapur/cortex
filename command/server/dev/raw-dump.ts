// Cortex Command — one-shot SDK raw dump (AUTHORIZED single real run).
//
// Runs ONE minimal real session the exact way Session does (mcp disabled via
// mcpServers:{} + strictMcpConfig:true, settingSources, claude_code preset,
// includePartialMessages, maxTurns 2) and prints every SDK message on one line
// so we can see how message_start / content_block indexes behave across the
// CLI's split deliveries of a single API assistant message (same message.id).
//
// Run: npx tsx dev/raw-dump.ts    (costs ~$1-2, <2 min, no MCP)

import { query } from "@anthropic-ai/claude-agent-sdk";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

function blockTypes(content: unknown): string[] {
  if (typeof content === "string") return ["<string>"];
  if (!Array.isArray(content)) return [];
  return content.map((b) =>
    b && typeof b === "object" ? String((b as { type?: unknown }).type ?? "?") : typeof b,
  );
}

async function main(): Promise<void> {
  const cwd = mkdtempSync(join(tmpdir(), "cortex-rawdump-"));
  console.log(`cwd=${cwd}`);
  let n = 0;
  try {
    const q = query({
      prompt: "Think briefly about what 2+2 is, then answer with just the number.",
      options: {
        cwd,
        settingSources: ["user", "project", "local"],
        systemPrompt: { type: "preset", preset: "claude_code" },
        includePartialMessages: true,
        maxTurns: 2,
        mcpServers: {},
        strictMcpConfig: true,
      },
    });
    for await (const msg of q) {
      n++;
      const any = msg as any;
      if (msg.type === "system") {
        console.log(`#${n} system/${any.subtype} model=${any.model ?? ""}`);
      } else if (msg.type === "stream_event") {
        const ev = any.event ?? {};
        let extra = "";
        if (ev.type === "message_start") extra = `msgid=${ev.message?.id}`;
        else if (ev.type === "content_block_start") extra = `idx=${ev.index} cb=${ev.content_block?.type}`;
        else if (ev.type === "content_block_delta") extra = `idx=${ev.index} delta=${ev.delta?.type}`;
        else if (ev.type === "content_block_stop") extra = `idx=${ev.index}`;
        else if (ev.type === "message_delta") extra = `stop=${ev.delta?.stop_reason ?? ""}`;
        console.log(`#${n} stream_event/${ev.type} ${extra} parent=${any.parent_tool_use_id ?? null}`);
      } else if (msg.type === "assistant" || msg.type === "user") {
        const m = any.message ?? {};
        console.log(
          `#${n} ${msg.type} msgid=${m.id ?? "-"} parent=${any.parent_tool_use_id ?? null} blocks=[${blockTypes(m.content).join(",")}]`,
        );
      } else if (msg.type === "result") {
        console.log(`#${n} result/${any.subtype} cost=${any.total_cost_usd}`);
      } else {
        console.log(`#${n} ${msg.type}`);
      }
    }
  } finally {
    try {
      rmSync(cwd, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
    console.log(`cleaned ${cwd}`);
  }
}

main()
  .then(() => process.exit(0))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
