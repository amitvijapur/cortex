---
name: cortex-frontend-design
description: Use Cortex's frontend design library to find references, plan visual work, select relevant design guidance, or capture reusable frontend discoveries across projects.
---

# Cortex frontend library

This skill points to one maintained library in the Cortex checkout. Resolve this
SKILL.md's real path when installed through a symlink; `../../frontend/README.md`
from its directory is the library entry point. Read that entry point first.
If the checkout moved, report the broken link and use the project's own design
brief until the dedicated installer is rerun from the new location.

For design work, inspect the project's brief, tokens and constraints before
selecting library references. Project requirements take precedence over the
library's aesthetic suggestions. Load only the relevant guidance:

| Need | Library file |
| --- | --- |
| New interface or visual direction | guidance/PLAYBOOK.md, then the relevant prompt in guidance/PROMPT-PACK.md |
| Existing interface critique or hardening | Relevant sections of guidance/CHECKLISTS.md |
| Find a reference, book or implementation resource | resources.json; search title, purpose, tags and category |
| Choose specialist work | guidance/SKILL-MAP.md |
| Capture a discovery or a lesson from a project | README.md contribution instructions |

The skill map records workflows that informed the original kit. Check the active
session's skill catalogue before choosing one. A historical name or file on disk
does not prove a tool is callable. Use available equivalents or the guidance
directly; adding a resource does not install its tools.

Explain the relevance of the small set of references selected. Distinguish
inspiration, documentation, and project-tested evidence. The dated legacy guide is
an archival reading copy; maintained guidance and resources.json are authoritative.
Verify current APIs with official documentation when implementing a dependency.

When asked to add a resource, update resources.json once, validate and rebuild the
directory using the scripts documented in README.md. Record source, purpose,
tags, and meaningful notes. Only mark a resource tested when there is concrete
project evidence. At a project milestone, propose useful discoveries and lessons;
do not silently turn them into universal design rules. Keep private screenshots,
paid assets, client identities, and local file paths in the local companion folder.

Jaspr remains an optional reference if it comes up; do not install it or change
a project's stack just because it appears in the library. Flutter and Dart can
be catalogued with explicit platform tags when relevant to a project.
