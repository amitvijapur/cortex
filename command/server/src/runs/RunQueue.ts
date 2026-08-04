// Cortex Command — RunQueue (M2, typed stub).
//
// The autonomous run-queue is milestone M2. This file lands the typed surface
// now so imports and the shared Job contract are wired, but every operation is
// an explicit "not implemented" — no jobs.jsonl persistence, no run profile
// wiring, no FIFO scheduling yet. M1 ships the chat core only.
//
// Design (for M2, per the plan): jobs are metadata over ordinary run-profile
// Sessions; FIFO with 1 concurrent run; completion distilled from the session's
// ResultMessage; append-only jobs.jsonl (last row per job wins); on restart a
// `running` job becomes `interrupted` with one-click resume via sdkSessionId.

import type { Job, JobKind, JobResult } from "@cortex-command/shared";
import type { SessionManager } from "../session/SessionManager.js";

export interface EnqueueJobInput {
  kind: JobKind;
  prompt: string;
  cwd: string;
  title?: string | null;
}

const NOT_IMPLEMENTED = "RunQueue is M2 — not implemented in M1";

export class RunQueue {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(private readonly _manager: SessionManager) {}

  /** Enqueue an autonomous run. */
  enqueue(_input: EnqueueJobInput): Job {
    throw new Error(NOT_IMPLEMENTED);
  }

  list(): Job[] {
    return [];
  }

  get(_jobId: string): Job | undefined {
    return undefined;
  }

  cancel(_jobId: string): boolean {
    throw new Error(NOT_IMPLEMENTED);
  }

  /** Distill a JobResult from a completed session's turn.result (M2). */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private _distill(_result: unknown): JobResult {
    throw new Error(NOT_IMPLEMENTED);
  }
}
