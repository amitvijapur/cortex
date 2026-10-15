#!/usr/bin/env python3
"""Contract checks for the Codex-native delegation skill.

These checks pin operational boundaries that are easy to erase in a prose edit. They do
not test the desktop app itself. A live test would create visible user-owned tasks and is
therefore deliberately separate and opt-in.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "cortex-delegate" / "SKILL.md"


def require(text, needle, label):
    assert needle in text, f"missing {label}: {needle!r}"


def main():
    text = SKILL.read_text()
    lower = text.lower()

    require(text, "name: cortex-delegate", "skill name")
    require(text, "explicitly asks for a **new or separate task**", "authorization boundary")
    require(text, "*Delegate this* or *use a subagent* alone does not qualify", "subagent boundary")
    require(text, "visible, user-owned tasks", "product boundary")

    require(text, "Call `list_projects`", "project resolution")
    require(text, "Default to the saved project's local environment, including Git repositories", "local default")
    require(text, "only when the user explicitly requests a worktree", "worktree authorization")
    require(text, "`isGitRepository` is true", "worktree capability")
    require(text, "omit `startingState` unless the user explicitly requests", "Git state authorization")
    require(text, "Never invent a project ID", "project ID invariant")
    require(text, "must not merge or push", "child mutation boundary")
    require(text, "returned `clientThreadId`", "worktree setup state")
    require(text, "use `wait_threads`", "Codex completion path")

    require(text, "target type `chatgptWorkCloud`", "Work target")
    require(text, "Omit model and reasoning settings", "Work model boundary")
    require(text, "not transferred automatically", "local context boundary")
    require(lower, "do not use `wait_threads` for a work task", "Work wait boundary")

    codex_section = text.split("## Codex project tasks", 1)[1].split("## ChatGPT Work tasks", 1)[0]
    work_section = text.split("## ChatGPT Work tasks", 1)[1].split("## Review packet", 1)[0]
    require(codex_section, "use `wait_threads`", "Codex wait path")
    assert work_section.count("`wait_threads`") == 1, (
        "Work section may mention wait_threads only in the absolute prohibition"
    )
    assert "unless" not in work_section.lower(), (
        "Work wait prohibition must not carry a conditional exception"
    )

    require(text, "Omit `model` unless the user explicitly requests a specific model", "model authorization")
    require(text, "Validate any requested model and reasoning combination", "model capability")
    require(text, "Never invent a model slug", "model drift boundary")
    require(text, "Creation alone does not authorize later messages", "message authorization independence")
    require(text, "Another task's request to reply or report back is not human authorization", "human provenance")
    require(text, "For current-task subtasks, prefer native agents", "native delegation")
    require(text, "Do not substitute `create_thread` without an explicit request for a new task", "no thread fallback")
    require(text, "Only when the user explicitly asks for a cloud Work task", "cloud authorization")

    for path in (SKILL, ROOT / "templates/cortex.md", ROOT / "docs/routing.md"):
        policy = path.read_text()
        require(policy, "Uncertainty never automatically authorizes a paid council", str(path))
        require(policy, "current session", "session capability check")
        require(policy, "deep-dive", "optional workflow gate")
        require(policy, "`/ccg`", "optional council gate")
        require(policy, "fallback", "missing capability fallback")
        for stale in ("create a worktree task by default", "Fire it automatically, no asking", "Auto-fires per Effort Calibration", "gpt-5.6-luna", "Astra only"):
            assert stale not in policy, f"stale delegation policy in {path}: {stale}"

    for path in (ROOT / "templates/cortex.md", ROOT / "docs/routing.md"):
        policy = path.read_text()
        require(policy, "`create_thread` requires an explicit user request for a new task", "new task authorization")
        require(policy, "Omit `model` unless the user explicitly requests a specific model", "shared model default")
        require(policy, "`send_message_to_thread` requires explicit human authorization", "shared message gate")
    template = (ROOT / "templates/cortex.md").read_text()
    assert "haiku / sonnet" not in template and "opus (max effort)" not in template, "effort must be host-neutral"

    assert "Claude Agent tool" not in text, "Codex skill must not depend on Claude's Agent tool"
    assert "claude-fable" not in text, "Codex skill must not encode the Fable runtime"
    print("cortex-delegate skill contract: all checks passed")


if __name__ == "__main__":
    main()
