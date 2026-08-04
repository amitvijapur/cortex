import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + WS to the Express/ws backend on :7788 so the
// browser only ever talks to Vite in dev. Production serves web/dist from
// the same Express process, so no proxy is needed there.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: "http://127.0.0.1:7788", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:7788", ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
  },
});
