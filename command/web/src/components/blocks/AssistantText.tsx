// Cortex Command — streaming assistant text with minimal markdown.
// A blinking caret shows while the block is still streaming (not done).

import { renderMarkdown } from "../../lib/markdown";

export function AssistantText({
  text,
  done,
}: {
  text: string;
  done: boolean;
}): React.ReactNode {
  return (
    <div className="turn turn-assistant">
      <div className="turn-body assistant-body">
        {renderMarkdown(text)}
        {!done && <span className="stream-caret" aria-hidden="true" />}
      </div>
    </div>
  );
}
