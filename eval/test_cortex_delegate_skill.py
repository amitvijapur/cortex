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
    require(text, "create a worktree task by default", "Git isolation default")
    require(text, "For a saved non-Git project, use its local environment", "non-Git environment")
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

    require(text, "gpt-5.6-luna", "mechanical worker")
    require(text, "gpt-5.6-terra", "standard worker")
    require(text, "gpt-5.6-sol", "complex worker")
    require(text, "Astra only for a second hard problem", "Astra reservation")
    require(text, "using only models exposed in the current session", "model availability rule")
    require(text, "Never invent a model slug", "model drift boundary")

    assert "Claude Agent tool" not in text, "Codex skill must not depend on Claude's Agent tool"
    assert "claude-fable" not in text, "Codex skill must not encode the Fable runtime"
    print("cortex-delegate skill contract: all checks passed")


if __name__ == "__main__":
    main()
