// Cortex Command — PreToolUse hooks.
//
// Two hooks, both keyed off the profile's own allowlist (via isProfileAllowed):
//
//  - ASK hook (both profiles): the SDK's own stdout warns "Allow rules from
//    settings files can also shadow the callback" — a user-level `permissions.allow`
//    entry (loaded via settingSources) auto-approves a tool BEFORE canUseTool is
//    consulted, so chat Bash would run with no card. This hook closes that hole:
//    for anything the profile does NOT genuinely auto-approve, it returns
//    permissionDecision:"ask", which forces the SDK through canUseTool
//    regardless of settings-file allow rules. Genuinely-allowlisted calls return
//    {} (no opinion) so they stay auto-approved.
//
//  - DENY hook (run profile only): the hard denylist (sudo, rm -rf outside the
//    project, force-push, curl|sh, …). Composed BEFORE the ask hook so deny wins.
//
// Composition (Session.buildOptions): chat → [ask]; run → [deny, ask]. On run,
// Bash is bare-allowlisted so the ask hook returns {} for it (correct: run's
// broad Bash auto-runs; only the denylist gates it).
//
// The decision cores are exported as pure functions so they can be unit-tested
// directly — a scripted fake query cannot execute real SDK hook plumbing.

import type {
  HookCallbackMatcher,
  HookInput,
  HookJSONOutput,
} from "@anthropic-ai/claude-agent-sdk";
import type { PermissionProfile } from "@cortex-command/shared";
import { isProfileAllowed, matchesRunDenylist } from "./profiles.js";

const NO_OPINION: HookJSONOutput = {};

/** Pure core of the ask hook. Returns "ask" unless the profile auto-approves. */
export function askHookDecision(
  profile: PermissionProfile,
  cwd: string,
  toolName: string,
  input: unknown,
): HookJSONOutput {
  if (isProfileAllowed(profile, toolName, input, cwd)) return NO_OPINION;
  return {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason:
        "Not auto-approved by the session profile — operator approval required.",
    },
  };
}

/** Pure core of the deny hook. Returns "deny" for hard-denylisted commands. */
export function denyHookDecision(
  profile: PermissionProfile,
  toolName: string,
  input: unknown,
): HookJSONOutput {
  if (profile.denyPatterns.length === 0) return NO_OPINION;
  const verdict = matchesRunDenylist(toolName, input);
  if (verdict.denied) {
    return {
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: verdict.reason ?? "denied by run denylist",
      },
    };
  }
  return NO_OPINION;
}

/** Narrow a hook input to its PreToolUse tool_name/tool_input. */
function preToolUseFields(input: HookInput): { toolName: string; toolInput: unknown } | null {
  if (input.hook_event_name === "PreToolUse") {
    return { toolName: input.tool_name, toolInput: input.tool_input };
  }
  return null;
}

export function makeAskHook(profile: PermissionProfile, cwd: string): HookCallbackMatcher {
  return {
    hooks: [
      async (input): Promise<HookJSONOutput> => {
        const f = preToolUseFields(input);
        return f ? askHookDecision(profile, cwd, f.toolName, f.toolInput) : NO_OPINION;
      },
    ],
  };
}

export function makeDenyHook(profile: PermissionProfile): HookCallbackMatcher {
  return {
    hooks: [
      async (input): Promise<HookJSONOutput> => {
        const f = preToolUseFields(input);
        return f ? denyHookDecision(profile, f.toolName, f.toolInput) : NO_OPINION;
      },
    ],
  };
}
