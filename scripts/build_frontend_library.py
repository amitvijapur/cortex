#!/usr/bin/env python3
"""Build a deterministic, offline frontend directory and Markdown references."""
import argparse
import html
from pathlib import Path
import sys

from validate_frontend_library import ROOT, STATUSES, ValidationError, load_catalogue

STYLE = '''
:root{color-scheme:light;--paper:#f6f1e7;--ink:#292720;--rust:#913f2b;--line:#ccc3b4}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}
a{color:var(--rust);text-underline-offset:3px}a:hover{text-decoration-thickness:2px}a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,#entries:focus-visible{outline:3px solid var(--rust);outline-offset:4px}
.skip-link{position:absolute;left:20px;top:0;transform:translateY(-150%);background:var(--ink);color:var(--paper);padding:12px 18px;z-index:1}.skip-link:focus{transform:translateY(0)}
.wrap{max-width:1120px;margin:auto;padding:32px 28px}nav{display:flex;flex-wrap:wrap;gap:12px 24px;font-size:.85rem;border-bottom:1px solid var(--line);padding-bottom:20px}
header{padding:44px 0 28px}.eyebrow{text-transform:uppercase;letter-spacing:.16em;font-size:.73rem;color:var(--rust);font-weight:700}
h1{font:clamp(2.8rem,7vw,5.2rem)/1.05 Georgia,serif;letter-spacing:-.04em;margin:12px 0 20px}header p{max-width:640px;color:#625b50}
.filters{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:16px;padding:22px 0;border-block:1px solid var(--line)}label{display:block;font-size:.76rem;font-weight:700;letter-spacing:.04em}
input,select{display:block;width:100%;margin-top:7px;padding:10px;border:1px solid #a89e8e;background:#fffaf2;color:var(--ink);border-radius:0;font:inherit;min-height:44px}
.count{font-size:.83rem;color:#625b50;margin:20px 0}.entries{list-style:none;padding:0;margin:0}.entry{display:grid;grid-template-columns:170px 1fr;gap:24px;border-top:1px solid var(--line);padding:22px 0}
.meta{font-size:.75rem;color:#625b50}.category{font-weight:700;color:var(--rust);margin-bottom:8px}.status{text-transform:capitalize}h2{font:1.45rem/1.2 Georgia,serif;margin:0 0 9px}h2 a{color:var(--ink)}.purpose{margin:0 0 9px;max-width:760px}.tags{font-size:.76rem;color:var(--rust)}details{font-size:.83rem;color:#625b50;margin-top:10px}summary{cursor:pointer;width:fit-content}details p{white-space:pre-wrap;overflow-wrap:anywhere}
.entry>div{min-width:0;overflow-wrap:anywhere}[hidden]{display:none!important}.empty{padding:35px 0;border-top:1px solid var(--line)}footer{border-top:1px solid var(--line);padding-top:20px;margin-top:28px;font-size:.78rem;color:#625b50}
@media(max-width:700px){.wrap{padding:20px}.filters{grid-template-columns:1fr 1fr}.search{grid-column:1/-1}.entry{grid-template-columns:1fr;gap:10px}.meta{display:flex;flex-wrap:wrap;gap:8px 16px}.category{margin:0}header{padding-top:30px}}
'''

SCRIPT = '''
(() => {
  const controls = document.querySelector('.filters');
  const search = document.getElementById('search');
  const category = document.getElementById('category');
  const kind = document.getElementById('kind');
  const status = document.getElementById('status');
  const entries = Array.from(document.querySelectorAll('.entry'));
  function update() {
    const terms = search.value.toLocaleLowerCase().trim().split(/\\s+/).filter(Boolean);
    let count = 0;
    for (const entry of entries) {
      const matches = terms.every(term => entry.dataset.search.includes(term)) &&
        (!category.value || entry.dataset.category === category.value) &&
        (!kind.value || entry.dataset.kind === kind.value) &&
        (!status.value || entry.dataset.status === status.value);
      entry.hidden = !matches;
      if (matches) count++;
    }
    document.getElementById('count').textContent = `${count} of ${entries.length} entries`;
    document.getElementById('empty').hidden = count !== 0;
  }
  controls.hidden = false;
  controls.addEventListener('input', update);
  controls.addEventListener('change', update);
  update();
})();
'''


def esc(value):
    return html.escape(str(value), quote=True)


def options(values):
    return ''.join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values)


def render_site(records):
    rows = []
    for r in records:
        title = esc(r['title'])
        if r['kind'] == 'resource':
            title = f'<a href="{esc(r["url"])}" rel="noopener noreferrer">{title}</a>'
        searchable = ' '.join(str(v) if not isinstance(v, list) else ' '.join(v) for v in r.values()).lower()
        rows.append(f'''<li class="entry" id="{esc(r['id'])}" data-category="{esc(r['category'])}" data-kind="{r['kind']}" data-status="{r['status']}" data-search="{esc(searchable)}">
<div class="meta"><div class="category">{esc(r['category'])}</div><div>{r['kind'].title()} · <span class="status">{r['status']}</span></div></div>
<div><h2>{title}</h2><p class="purpose">{esc(r['purpose'])}</p><div class="tags">{esc(' · '.join(r['tags']))}</div>
<details><summary>Reference notes</summary><p>{esc(r['notes'])}</p><p>Used in: {esc(', '.join(r['used_in']) or 'No recorded projects')}<br>Added: {r['added']} · Last checked: {r['last_checked'] or 'Not checked'}</p></details></div></li>''')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Cortex frontend reference library: tools, inspiration, and books."><title>Frontend library · Cortex</title><style>{STYLE}</style></head>
<body><a class="skip-link" href="#entries">Skip to entries</a><main class="wrap"><nav aria-label="Library navigation"><a href="../guidance/PLAYBOOK.md">Playbook</a><a href="../guidance/PROMPT-PACK.md">Prompt pack</a><a href="../guidance/CHECKLISTS.md">Checklists</a><a href="../guidance/SKILL-MAP.md">Skill map</a><a href="../REFERENCES.md">All references</a><a href="../legacy/index.html">Original guide · 5 Sep</a></nav>
<header><div class="eyebrow">Cortex / The reference shelf</div><h1>Frontend library.</h1><p>A working directory of tools, ideas, and books for thoughtful interfaces. Find a reference, check its context, and make it your own.</p></header>
<section class="filters" aria-label="Filter the library" hidden><label class="search" for="search">Search the library<input id="search" type="search" placeholder="Try typography, motion, or accessibility"></label>
<label for="category">Category<select id="category"><option value="">All categories</option>{options(sorted({r['category'] for r in records}))}</select></label>
<label for="kind">Type<select id="kind"><option value="">All types</option>{options(('resource', 'book'))}</select></label>
<label for="status">Status<select id="status"><option value="">All statuses</option>{options(STATUSES)}</select></label></section>
<noscript><p>All entries are shown below. Enable JavaScript to search and filter.</p></noscript>
<p class="count" id="count" role="status" aria-live="polite" aria-atomic="true">{len(records)} of {len(records)} entries</p>
<ul class="entries" id="entries" tabindex="-1" aria-label="Library entries">{''.join(rows)}</ul><p id="empty" class="empty"{'' if not records else ' hidden'}>No matching entries. Try fewer search terms or select all categories, types, and statuses.</p>
<footer>Curated references, not endorsements. Status and notes capture what has actually been tried.</footer></main><script>{SCRIPT}</script></body></html>
'''


def md(value):
    # Escape Markdown syntax as well as raw HTML. No Markdown is evaluated.
    value = esc(value).replace('\n', ' ').replace('\r', ' ')
    for character in '\\`*_{}[]()#+-.!|>':
        value = value.replace(character, '\\' + character)
    return value


def render_references(records):
    lines = ['# Frontend references', '', 'Generated from `resources.json`. Do not edit by hand.', '',
             '[Browse the directory](site/index.html) · [Playbook](guidance/PLAYBOOK.md) · [Prompt pack](guidance/PROMPT-PACK.md) · [Checklists](guidance/CHECKLISTS.md) · [Skill map](guidance/SKILL-MAP.md) · [Original guide · 5 Sep](legacy/index.html)', '']
    for r in records:
        lines += [f'## {md(r["title"])}', '', f'{md(r["category"])} · {r["kind"]} · {r["status"]}', '', md(r['purpose']), '']
        if r['kind'] == 'resource':
            # Angle destination plus percent-encoding prevents Markdown link injection.
            url = r['url'].replace('<', '%3C').replace('>', '%3E').replace('"', '%22')
            lines += [f'[Visit resource](<{url}>)', '']
        lines += [f'Tags: {md(", ".join(r["tags"]))}', '', md(r['notes']), '',
                  f'Used in: {md(", ".join(r["used_in"]) or "No recorded projects")}', '',
                  f'Added: {r["added"]}. Last checked: {r["last_checked"] or "Not checked"}.', '']
    return '\n'.join(lines)


def build(root=ROOT, check=False):
    root = Path(root)
    records = sorted(load_catalogue(root), key=lambda r: (r['category'].casefold(), r['title'].casefold(), r['id']))
    outputs = {root / 'frontend/site/index.html': render_site(records),
               root / 'frontend/REFERENCES.md': render_references(records)}
    drift = []
    for path, content in outputs.items():
        expected = content.encode('utf-8')
        if not path.exists() or path.read_bytes() != expected:
            drift.append(path.relative_to(root).as_posix())
    if check:
        if drift:
            raise ValidationError('generated output drift: ' + ', '.join(drift))
    else:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode('utf-8'))
    return len(records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='repository root')
    parser.add_argument('--check', action='store_true', help='report drift without writing')
    args = parser.parse_args(argv)
    try:
        count = build(args.root, args.check)
    except (ValidationError, OSError) as exc:
        print(f'Build failed: {exc}', file=sys.stderr)
        return 1
    print(f'{"Checked" if args.check else "Built"} frontend library: {count} entries')
    return 0


if __name__ == '__main__':
    sys.exit(main())
