// Cortex Command — Bash tool body: the command, then a truncated output preview.

import type { ToolResultData } from "../../lib/store";

function commandOf(input: unknown): string {
  if (input && typeof input === "object") {
    const cmd = (input as Record<string, unknown>)["command"];
    if (typeof cmd === "string") return cmd;
  }
  return "";
}

function descriptionOf(input: unknown): string | null {
  if (input && typeof input === "object") {
    const d = (input as Record<string, unknown>)["description"];
    if (typeof d === "string" && d) return d;
  }
  return null;
}

export function BashCardBody({
  input,
  result,
}: {
  input: unknown;
  result?: ToolResultData;
}): React.ReactNode {
  const command = commandOf(input);
  const desc = descriptionOf(input);
  return (
    <div className="tb">
      {desc && <div className="tb-desc">{desc}</div>}
      {command && (
        <div className="tb-section">
          <div className="tb-label">$ command</div>
          <pre className="codeblock">{command}</pre>
        </div>
      )}
      {result && (
        <div className="tb-section">
          <div className="tb-label">
            output
            {result.truncated && <span className="tb-trunc"> · truncated</span>}
          </div>
          <pre className={"codeblock" + (result.isError ? " tb-err-out" : "")}>
            {result.preview || "(no output)"}
          </pre>
          {result.truncated && result.outputRef && (
            <a className="tb-viewfull" href={result.outputRef} target="_blank" rel="noreferrer">
              view full output
              {typeof result.fullLength === "number" ? ` (${result.fullLength} chars)` : ""}
            </a>
          )}
        </div>
      )}
    </div>
  );
}
