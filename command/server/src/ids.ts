// Cortex Command — id generation.
//
// ULID: 48-bit millisecond timestamp + 80 bits of randomness, Crockford base32.
// Lexicographically sortable by creation time, collision-safe, dependency-free.

import { randomBytes } from "node:crypto";

const ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // Crockford base32 (no I,L,O,U)
const TIME_LEN = 10;
const RAND_LEN = 16;

function encodeTime(now: number): string {
  let out = "";
  let t = now;
  for (let i = TIME_LEN - 1; i >= 0; i--) {
    const mod = t % 32;
    out = ENCODING[mod] + out;
    t = (t - mod) / 32;
  }
  return out;
}

function encodeRandom(): string {
  const bytes = randomBytes(RAND_LEN);
  let out = "";
  for (let i = 0; i < RAND_LEN; i++) {
    out += ENCODING[(bytes[i] ?? 0) % 32];
  }
  return out;
}

export function ulid(now: number = Date.now()): string {
  return encodeTime(now) + encodeRandom();
}

export const newSessionKey = (): string => `sess_${ulid()}`;
export const newApprovalId = (): string => `appr_${ulid()}`;
export const newJobId = (): string => `job_${ulid()}`;
