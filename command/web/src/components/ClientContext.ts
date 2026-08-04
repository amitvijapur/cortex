// Cortex Command — React context carrying the active Client (WS or demo).
// Cards/composer call client.* without threading props through the tree.

import { createContext, useContext } from "react";
import type { Client } from "../lib/ws";

export const ClientContext = createContext<Client | null>(null);

export function useClient(): Client {
  const c = useContext(ClientContext);
  if (!c) throw new Error("ClientContext not provided");
  return c;
}
