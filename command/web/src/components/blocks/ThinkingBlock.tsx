// Cortex Command — collapsed-by-default thinking block.

import { useState } from "react";

export function ThinkingBlock({
  text,
  done,
}: {
  text: string;
  done: boolean;
}): React.ReactNode {
  const [open, setOpen] = useState(false);
  return (
    <div className={"thinking" + (open ? " open" : "")}>
      <button className="thinking-h" onClick={() => setOpen((o) => !o)}>
        <span className="thinking-chev">{open ? "▾" : "▸"}</span>
        <span className="thinking-label mono">thinking{done ? "" : "…"}</span>
        {!open && <span className="thinking-peek">{text.slice(0, 80)}</span>}
      </button>
      {open && <div className="thinking-body">{text}</div>}
    </div>
  );
}
