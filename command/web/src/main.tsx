// Cortex Command — web entrypoint. Mounts the App; ReasonBlocks tokens plus the
// component layer (command.css) style it. ?demo=1 drives the whole UI from a
// canned fixture (see dev/demo.ts) with no server.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/reasonblocks.css";
import "./styles/command.css";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
