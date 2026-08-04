// Cortex Command — permission profiles.
//
// A profile's `allowedTools` are passed to the SDK's `allowedTools` option:
// those tools auto-approve and NEVER reach `canUseTool`. Everything else routes
// through canUseTool → a PendingApproval card. File edits are scoped to the
// project via Claude Code's absolute-path rule syntax `Tool(//abs/path/**)`.
//
// The `run` profile (M2) additionally allows broad Bash but enforces a hard
// denylist through a PreToolUse deny hook — those never surface as an approvable
// card. The denylist matcher is defined here and unit-drivable now, ahead of
// RunQueue wiring.

import { isAbsolute, resolve, sep } from "node:path";
import type {
  PermissionProfile,
  PermissionProfileName,
} from "@cortex-command/shared";
import { CHAT_APPROVAL_TIMEOUT_MS, RUN_APPROVAL_TIMEOUT_MS } from "../config.js";

const CHAT_BASE_TOOLS = ["Read", "Glob", "Grep", "TodoWrite", "Task", "WebFetch", "WebSearch"];
const SCOPED_EDIT_TOOLS = ["Edit", "Write", "MultiEdit", "NotebookEdit"];

/** Strip trailing slashes (keep root as "/"). */
export function normalizeCwd(cwd: string): string {
  return cwd.replace(/\/+$/, "") || "/";
}

/**
 * A project-scoped auto-approve rule, e.g. cwd `/Users/amit/proj` →
 * `Edit(//Users/amit/proj/**)`. The double-slash prefix anchors the pattern to
 * the filesystem root (absolute), per Claude Code permission-rule syntax.
 */
export function scopedRule(tool: string, cwd: string): string {
  return `${tool}(/${normalizeCwd(cwd)}/**)`;
}

export function chatProfile(cwd: string): PermissionProfile {
  return {
    name: "chat",
    allowedTools: [...CHAT_BASE_TOOLS, ...SCOPED_EDIT_TOOLS.map((t) => scopedRule(t, cwd))],
    denyPatterns: [],
    approvalTimeoutMs: CHAT_APPROVAL_TIMEOUT_MS,
  };
}

/** Human-readable descriptions of the run-profile hard denylist. */
export const RUN_DENY_PATTERNS = [
  "sudo / privilege escalation",
  "rm -rf outside the project directory",
  "git push --force / force-with-lease",
  "curl|wget piped to a shell (curl … | sh)",
  "shutdown / reboot / halt / diskutil",
  "writes redirected outside the project directory",
];

export function runProfile(cwd: string): PermissionProfile {
  return {
    name: "run",
    allowedTools: [
      ...CHAT_BASE_TOOLS,
      ...SCOPED_EDIT_TOOLS.map((t) => scopedRule(t, cwd)),
      "Bash",
    ],
    denyPatterns: RUN_DENY_PATTERNS,
    approvalTimeoutMs: RUN_APPROVAL_TIMEOUT_MS,
  };
}

export function resolveProfile(name: PermissionProfileName, cwd: string): PermissionProfile {
  return name === "run" ? runProfile(cwd) : chatProfile(cwd);
}

// --------------------------------------------------------------------------- //
// Run-profile hard denylist matcher (enforced via PreToolUse deny in M2)
// --------------------------------------------------------------------------- //

const DENY_RULES: Array<{ re: RegExp; reason: string }> = [
  { re: /\bsudo\b/, reason: "privilege escalation (sudo) is denied" },
  { re: /\brm\s+-[a-z]*r[a-z]*f?\b.*(\s\/(?!\/)|\s~|\s\$HOME)/, reason: "rm -rf outside the project is denied" },
  { re: /\bgit\s+push\b.*(--force\b|--force-with-lease\b|\s-f\b|\s\+)/, reason: "force-push is denied" },
  { re: /\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(sh|bash|zsh)\b/, reason: "curl|sh piping to a shell is denied" },
  { re: /\b(shutdown|reboot|halt|diskutil)\b/, reason: "system/disk control is denied" },
];

/**
 * Decide whether a tool call trips the run-profile hard denylist. Bash-command
 * oriented; non-Bash tools are never denied here (file writes are scoped via
 * allowedTools instead).
 */
export function matchesRunDenylist(
  toolName: string,
  input: unknown,
): { denied: boolean; reason?: string } {
  if (toolName !== "Bash") return { denied: false };
  const command =
    input && typeof input === "object" && "command" in input
      ? String((input as Record<string, unknown>)["command"] ?? "")
      : "";
  if (!command) return { denied: false };
  for (const rule of DENY_RULES) {
    if (rule.re.test(command)) return { denied: true, reason: rule.reason };
  }
  return { denied: false };
}

// --------------------------------------------------------------------------- //
// Profile allow-check (the single source of truth for "auto-approved?")
// --------------------------------------------------------------------------- //
//
// This is the authority the PreToolUse ask-hook consults so that settings-file
// allow rules (loaded via settingSources) cannot shadow canUseTool: anything
// this returns false for is forced to `ask`. It is derived from the profile's
// own allowedTools so the rule strings live in exactly one place.

/** Whether an absolute/relative path resolves inside cwd (no `..` escape). */
export function isPathInsideCwd(p: string, cwd: string): boolean {
  if (!p) return false;
  const base = normalizeCwd(cwd);
  const abs = isAbsolute(p) ? resolve(p) : resolve(base, p);
  return abs === base || abs.startsWith(base + sep);
}

/** Bare (unscoped) tool names a profile auto-approves, e.g. "Read", "Bash". */
function bareAllowlist(profile: PermissionProfile): Set<string> {
  const out = new Set<string>();
  for (const entry of profile.allowedTools) {
    if (!entry.includes("(")) out.add(entry);
  }
  return out;
}

/** Path-scoped tool names in a profile, e.g. Edit(//proj/**) → "Edit". */
function scopedAllowlist(profile: PermissionProfile): Set<string> {
  const out = new Set<string>();
  for (const entry of profile.allowedTools) {
    const m = /^([A-Za-z0-9_]+)\(/.exec(entry);
    if (m?.[1]) out.add(m[1]);
  }
  return out;
}

/** Tool-input keys that carry the edit target path (per built-in edit tool). */
const PATH_INPUT_KEYS = ["file_path", "notebook_path"];
function toolTargetPath(input: unknown): string | undefined {
  if (!input || typeof input !== "object") return undefined;
  const rec = input as Record<string, unknown>;
  for (const key of PATH_INPUT_KEYS) {
    const v = rec[key];
    if (typeof v === "string" && v) return v;
  }
  return undefined;
}

/**
 * Whether a tool call is genuinely permitted by the profile, independent of any
 * settings-file allow rules: bare-allowlisted names always; a scoped edit tool
 * only when its target path resolves inside cwd. Everything else (Bash on chat,
 * mcp__*, edits outside cwd, unknown tools) is NOT auto-approved → the ask-hook
 * forces canUseTool.
 */
export function isProfileAllowed(
  profile: PermissionProfile,
  toolName: string,
  input: unknown,
  cwd: string,
): boolean {
  if (bareAllowlist(profile).has(toolName)) return true;
  if (scopedAllowlist(profile).has(toolName)) {
    const target = toolTargetPath(input);
    return target !== undefined && isPathInsideCwd(target, cwd);
  }
  return false;
}

export type { PermissionProfileName };
