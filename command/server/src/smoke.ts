// SDK auth smoke test — run with:  npx tsx src/smoke.ts   (from command/server)
//
// Proves the plan's top risk is closed: that a spawned Node process can reach
// the Max-subscription auth (keychain) and complete a one-shot query. Prints
// the result subtype, session_id, total_cost_usd, and whether the reply text
// contained SMOKE_OK. On failure it captures the exact error and exits non-zero
// — no workarounds, just the diagnosis (per the task).

import { query } from "@anthropic-ai/claude-agent-sdk";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/** Pull concatenated text out of an assistant message's content blocks. */
function textOf(message: unknown): string {
  if (typeof message !== "object" || message === null) return "";
  const content = (message as { content?: unknown }).content;
  if (!Array.isArray(content)) return "";
  let out = "";
  for (const block of content) {
    if (
      block && typeof block === "object" &&
      (block as { type?: unknown }).type === "text" &&
      typeof (block as { text?: unknown }).text === "string"
    ) {
      out += (block as { text: string }).text;
    }
  }
  return out;
}

async function main(): Promise<void> {
  const cwd = mkdtempSync(join(tmpdir(), "cortex-smoke-"));
  console.log(`[smoke] temp cwd = ${cwd}`);

  let sessionId: string | null = null;
  let subtype: string | undefined;
  let costUsd: number | undefined;
  let assistantText = "";
  let resultText = "";

  try {
    const q = query({
      prompt: "Reply with exactly: SMOKE_OK",
      options: {
        cwd,
        settingSources: ["user", "project", "local"],
        systemPrompt: { type: "preset", preset: "claude_code" },
        maxTurns: 1,
      },
    });

    for await (const msg of q) {
      if (msg.type === "system" && msg.subtype === "init") {
        sessionId = msg.session_id;
        console.log(
          `[smoke] init: session_id=${msg.session_id} model=${msg.model} ` +
            `apiKeySource=${msg.apiKeySource}`,
        );
      } else if (msg.type === "assistant") {
        assistantText += textOf(msg.message);
      } else if (msg.type === "result") {
        subtype = msg.subtype;
        costUsd = msg.total_cost_usd;
        sessionId = msg.session_id ?? sessionId;
        if (msg.subtype === "success") resultText = msg.result;
      }
    }
  } catch (err) {
    console.error("[smoke] QUERY FAILED — auth or spawn error:");
    console.error(err instanceof Error ? (err.stack ?? err.message) : String(err));
    process.exit(1);
  }

  const containsOk = (assistantText + "\n" + resultText).includes("SMOKE_OK");

  console.log("-".repeat(56));
  console.log(`[smoke] result.subtype    = ${subtype ?? "(none received)"}`);
  console.log(`[smoke] session_id        = ${sessionId ?? "(none)"}`);
  console.log(`[smoke] total_cost_usd    = ${costUsd ?? "(none)"}`);
  console.log(
    `[smoke] assistant text    = ${JSON.stringify(assistantText.trim().slice(0, 200))}`,
  );
  console.log(`[smoke] contains SMOKE_OK = ${containsOk}`);
  console.log(
    `[smoke] AUTH              = ${
      subtype ? "OK — subscription reachable from spawned node process" : "UNKNOWN"
    }`,
  );

  process.exit(subtype && containsOk ? 0 : 2);
}

void main();
