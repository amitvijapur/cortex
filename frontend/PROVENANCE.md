# Frontend library provenance

Imported on 2026-09-13 from the `frontend-design-kit` source snapshot dated September 5, 2026. This is a local source import, not a new review of the linked websites. No external pages were fetched for this import.

## Preserved guidance and legacy snapshot

The following source files are copied unchanged into `guidance/`: `README.md`, `PLAYBOOK.md`, `PROMPT-PACK.md`, `CHECKLISTS.md`, `SKILL-MAP.md`, and `REFERENCES.md`.

`legacy/index.html` is an unchanged snapshot of the original `index.html`. Its stylesheet is embedded as a `data:text/css` URL, alongside a small inline style block. It does not require the source's separate `assets/field-manual.css`, so that redundant asset is not imported. The HTML has not been regenerated.

## HTML versus Markdown inspection

The HTML's main content presents the six guidance documents in this order: README, PLAYBOOK, SKILL-MAP, PROMPT-PACK, CHECKLISTS, REFERENCES. Comparing plain text extracted from that main content with the six Markdown documents produced the same ordered sequence of 5,716 words after ignoring formatting, whitespace, and punctuation. No unique prose was found in the HTML main content during this comparison. This is a content inspection, not a claim of identical markup or rendering.

The HTML adds a skip link, a table of contents, section anchors, rendered tables and disabled checklist inputs, page metadata, and its field-manual presentation. The embedded CSS includes responsive, print, reduced-motion, and increased-contrast treatments. These presentation details remain available in the legacy snapshot. They are not a separate source of catalog entries.

## Catalog derivation

`resources.json` contains exactly 53 entries derived only from `guidance/REFERENCES.md`: 46 URL resources and seven books. Source order, resource titles, URLs, and category headings are preserved. Book titles are preserved separately from author attribution, which remains in each book's notes together with its original reading-list wording, excluding Markdown emphasis marks. Books have no `url` field.

Purposes are concise descriptions derived from the source names and guidance. Tags and slug IDs are import metadata. Every entry starts with `status: "reference"`, `added: "2026-09-13"`, `last_checked: null`, and an empty `used_in` array. The added date records catalog import, not publication or link verification.

The original REFERENCES text and HTML state that links were checked on September 5, 2026. That historical source claim is preserved verbatim in those snapshots but has not been independently verified. No entry claims that its link was rechecked on the import date.

## Attribution and terms

The original attribution is preserved in both `guidance/README.md` and the legacy HTML:

> This is an original synthesis of working methods from Amit's installed design workflows and public frontend resources. It summarizes ideas rather than redistributing the original skill files. The public tools and libraries retain their own licenses and terms.

Book author credits and the public resource titles and URLs remain intact. This import does not grant new rights to the referenced tools, libraries, books, or websites, and does not redistribute their original skill files or book contents.

## Import verification

Verification covers byte equality of all seven copied files against the source, exact catalog counts and ordered title/URL correspondence, preserved book titles and author credits, schema and slug uniqueness, required default values, and absence of private machine paths in the imported content. Link availability and browser rendering are outside this data import verification.
