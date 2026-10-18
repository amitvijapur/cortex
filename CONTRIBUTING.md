# Contributing to Cortex

Start with a concrete task and the behavior you want to change. Small documentation fixes and reproducible onboarding reports are welcome. See [first-run feedback](docs/adoption-feedback.md) if you are trying Cortex for the first time.

## Local development

Use macOS or Linux with Bash, Git and Python 3.11 or newer. Work on a branch in a checkout, preserve unrelated edits and keep personal configuration and routing logs out of commits.

Run the default checks from the repository root:

```bash
bash scripts/run_checks.sh
```

This is the local entry point used by CI. It runs deterministic checks with isolated fixtures and dry-run evaluation paths. It does not authorize paid model evaluation or writing test routes into personal history. Inspect a failing check and rerun that check after fixing it.

For CLI changes, the required behavioral suite can also be run directly:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 eval/test_cortex_cli.py
```

Read [routing](docs/routing.md) before changing routing behavior and [evaluation](docs/evaluation.md) before changing retrieval or evaluation claims. Real model-backed evaluation requires an explicitly agreed scope and spend budget. New fixtures must use temporary state, not the contributor's agent home.

## Pull requests

Explain the problem, resulting behavior and checks you ran. Include a before/after example when it makes the change clearer. For documentation changes, check local links, anchors, actual CLI flags and state-root consistency. For visual changes, preserve the violet identity and include a readable preview.

Add meaningful regression coverage for runtime fixes. Avoid tests that only repeat implementation details. Keep fixture output separate from real adoption evidence and avoid claims of optimal routing, savings or universal host compatibility without measurements.

Report bugs through [GitHub issues](https://github.com/amitvijapur/cortex/issues). Include the revision, host, expected behavior and a minimal sanitized reproduction. Remove credentials and private task text before sharing command output.
