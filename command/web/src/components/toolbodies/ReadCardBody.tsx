// Cortex Command — Read tool body: file path + optional line range.

import type { ToolResultData } from "../../lib/store";

export function ReadCardBody({
  input,
  result,
}: {
  input: unknown;
  result?: ToolResultData;
}): React.ReactNode {
  const obj = input && typeof input === "object" ? (input as Record<string, unknown>) : {};
  const path = typeof obj["file_path"] === "string" ? (obj["file_path"] as string) : "";
  const offset = typeof obj["offset"] === "number" ? (obj["offset"] as number) : null;
  const limit = typeof obj["limit"] === "number" ? (obj["limit"] as number) : null;
  const range =
    offset !== null || limit !== null
      ? "lines " + (offset ?? 1) + (limit !== null ? "–" + ((offset ?? 1) + limit) : "→")
      : "whole file";

  return (
    <div className="tb">
      <div className="tb-readrow">
        <span className="tb-path mono">{path || "(no path)"}</span>
        <span className="tb-range mono">{range}</span>
      </div>
      {result && result.preview && (
        <pre className="codeblock tb-read-preview">{result.preview}</pre>
      )}
    </div>
  );
}
