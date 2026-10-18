# Contributor checks

Run the same selected checks as CI from the repository root:

```bash
bash scripts/run_checks.sh
```

The command requires Python 3.11 or newer, Git and Bash. It installs no packages
and makes no model requests. Runtime fixtures create disposable state rather than
using your installed routing log. Node.js is optional locally and compares the
generated logo lockups with their committed sources when present. CI's hosted
runners include Node.js. Social-card and demo rendering are separate maintainer
tasks, so contributors do not need graphics libraries to check a documentation
change.

## What runs

| Suite | Scope |
| --- | --- |
| `eval/test_cortex_cli.py` | CLI behavior, legacy rows, append-only events and doctor |
| `eval/test_cortex_integrity.py` | Concurrent writes, correction scope and atomic replacement |
| `eval/test_install_sync_integrity.py` | Installation, repeat installation and local sync fixtures |
| `eval/test_hint_selector.py` | Production history selection and isolated CLI behavior |
| `eval/test_host_identity.py` | Host/session provenance and isolated CLI behavior |
| `eval/test_cortex_delegate_skill.py` | Delegation skill authorization and capability contracts |
| `scripts/record_demo.py --check` | Real CLI walkthrough replay in fresh disposable state |
| `scripts/check_docs.py` | Maintained guide links, local anchors, SVG syntax and social-card format |

Two optional mixed CLI/intake-module tests skip because the private intake module
is not distributed in this repository. The runner unsets its optional fixture
override so local user configuration cannot enable it accidentally. This is a
bounded regression suite, not every evaluation in `eval/` or an assessment of
real model quality. Paid adviser evaluation and live integrations are excluded.

## CI matrix

[The workflow](../../.github/workflows/checks.yml) configures Python 3.11 and 3.14
on Ubuntu 24.04 and macOS 15. A configured job is not proof of compatibility;
check the actual run results before claiming a platform passed. Windows is not
covered, and runtime locking uses POSIX `fcntl`. The script was initially verified
locally with Python 3.14.7 on macOS.

The Actions checkout and Python setup steps require network access to GitHub and
may download the selected Python build. The subsequent test command is offline.
Actions use immutable commit pins, `contents: read`, and do not persist checkout
credentials. No secrets are required. Update pins by checking the action's
official release and commit, then rerun the matrix.

## Documentation checker boundaries

The checker reads root Markdown files, maintained guides under `docs/`, and the
evaluation and frontend READMEs. It ignores code examples, dated reports and the
historical work log and lessons. It checks relative files, images and heading
anchors, including HTML image attributes. It does not fetch external URLs or
interpret Markdown as a browser would. A parser pass does not replace a visual
review of the README or a live social-card check.

To inspect a particular Markdown file, pass its repository path:

```bash
python3 scripts/check_docs.py README.md
```

The complete run also requires canonical onboarding and product documentation,
validates SVG roots, and checks that `assets/cortex-social-preview.png` has a PNG
header, measures 1280 × 640 pixels and is smaller than 1 MB. The editable SVG must
exist. The demo GIF's signature is checked when present. It does not compare
rendered pixels with their sources; use the
[social-preview guide](social-preview.md) for that release check.
