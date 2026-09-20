# Cortex frontend design library

The maintained home for reusable frontend design guidance, references and lessons.
Open [the resource directory](site/index.html) to browse or filter the collection,
or read the [design playbook](guidance/PLAYBOOK.md) to begin a project.

## What to use

- [Prompt pack](guidance/PROMPT-PACK.md) for a brief, art direction and focused passes.
- [Checklists](guidance/CHECKLISTS.md) for critique, accessibility and delivery.
- [Skills map](guidance/SKILL-MAP.md) for responsibilities and workflow ideas.
- [Resource list](REFERENCES.md) for a readable export of the catalogue.
- [Original illustrated guide](legacy/index.html) for the dated 5 September snapshot.
- [Provenance](PROVENANCE.md) for the migration and attribution record.

Use the current project's own brief and design system first. The skills map is
historical reference, not an assertion that every named skill is available in the
current agent session. Check the session's actual catalogue before invoking one.

## Ownership

Edit `guidance/` for shared advice and `resources.json` for resources. The scripts
generate `REFERENCES.md` and `site/index.html`; never edit those outputs by hand.
`guidance/REFERENCES.md` and `legacy/` retain the original snapshot for provenance.
The original Desktop kit is preserved separately. This checkout is the maintained
master going forward; the legacy copy will not receive new resources.

## Find and grow the library

The directory supports text search and filters and works directly from disk.
Agents can search `resources.json` without loading the entire guide. From the
Cortex checkout, run:

```sh
python3 scripts/validate_frontend_library.py
python3 scripts/build_frontend_library.py
python3 scripts/build_frontend_library.py --check
```

To add a resource, create one catalogue object with a stable slug `id`, `title`,
`kind` (`resource` or `book`), `category`, `purpose`, `tags`, `status`, `added`,
`last_checked`, `notes`, and `used_in`. Web resources also have an HTTPS `url`.
Books do not need an invented link. Use the existing entries as examples.
Then validate and regenerate both views. Commit the source and generated changes
together after review. IDs remain stable when a title or URL changes.

Use `reference` for material worth consulting, `tested` for a resource supported
by recorded project evidence, `watch` for something to assess, and `archived` for
something superseded. `last_checked` is null until someone actually checks the
source. Record what was checked in notes; a reachable URL does not prove advice
is correct. An import date is not a verification date.

After a project, capture which resource helped, how it was used, the result, and
any limitations in `notes` and `used_in`. Only use public project identifiers
here. Repeated evidence can motivate an explicit playbook edit; usage counts
alone do not change routing defaults. Retain unsuccessful lessons too.

Adding resources never installs software. Jaspr remains optional and uninstalled;
platform-specific Flutter or Dart references can be added when useful.

## Private companion

Keep private screenshots, client work, purchased assets and personal project notes
under your agent state directory, for example `~/.claude/cortex-frontend-private/`.
That folder is outside this repository and is never read by the public generator.
Use a simple local Markdown index with source, license, purpose, project and result.
Only move material into the shared catalogue after deciding it is suitable to share.

## Use from any project

Run `bash scripts/install_frontend_library.sh` from this checkout. It links this
library's skill into existing Claude and Codex homes and exposes the library at
`cortex-frontend` in each home. It does not replace the Cortex CLI. New sessions can
discover `cortex-frontend-design`; existing sessions can read the library directly.

The links point to this checkout, so local edits are immediately available. Keep
the checkout in place and use a stable branch after review. If a link conflicts
with an existing file or points elsewhere, the installer reports it without
overwriting it. `CLAUDE_DIR` and `CODEX_DIR` allow isolated installation tests.
