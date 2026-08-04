// Cortex Command — fallback tool body: pretty-printed JSON input + output preview.

import type { ToolResultData } from "../../lib/store";

function pretty(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export function GenericJsonBody({
  input,
  result,
}: {
  input: unknown;
  result?: ToolResultData;
}): React.ReactNode {
  return (
    <div className="tb">
      {input !== undefined && (
        <div className="tb-section">
          <div className="tb-label">input</div>
          <pre className="codeblock">{pretty(input)}</pre>
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
            </a>
          )}
        </div>
      )}
    </div>
  );
}
