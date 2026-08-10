#!/usr/bin/env python3
"""apply_descriptions — write proposed descriptions into the agent roster.

WHY THIS IS A SCRIPT AND NOT 245 EDITS
    The rewrites are produced as proposals precisely so that applying them is one
    reviewable, reversible act. Every file is backed up first, under a single timestamped
    directory, so undoing is one `cp -r` rather than 245 individual reverts.

WHAT IT WILL NOT DO
    Touch anything but the `description:` field of the YAML frontmatter. It does not
    reformat, reorder keys, or rewrite bodies. If a file's frontmatter cannot be parsed
    confidently it is skipped and reported rather than guessed at — a mangled agent file
    is worse than an unfindable one.
"""
import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
# A frontmatter key runs until the next top-level key or the end of the block, so a
# multi-line quoted description has to be consumed whole rather than line-by-line.
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):", re.M)


def replace_description(text: str, new_desc: str) -> str | None:
    m = FM_RE.match(text)
    if not m:
        return None
    head = m.group(1)
    keys = [(k.start(), k.group(1)) for k in KEY_RE.finditer(head)]
    span = None
    for i, (pos, key) in enumerate(keys):
        if key.lower() == "description":
            end = keys[i + 1][0] if i + 1 < len(keys) else len(head)
            span = (pos, end)
            break
    # Quote and escape so a description containing a colon or quote cannot corrupt the
    # block. Single-line double-quoted is the form the roster already uses.
    safe = new_desc.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()
    entry = f'description: "{safe}"\n'
    if span is None:
        new_head = head.rstrip() + "\n" + entry
    else:
        new_head = head[:span[0]] + entry + head[span[1]:]
    return f"---\n{new_head.rstrip()}\n---\n" + text[m.end():]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposals", nargs="+", required=True)
    ap.add_argument("--tiers", default="eval/proposals/rewrite-tiers.json")
    ap.add_argument("--backup-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paths = json.loads(Path(args.tiers).read_text())["paths"]
    proposed: dict[str, str] = {}
    for p in args.proposals:
        d = json.loads(Path(p).read_text())
        d = d.get("descriptions", d) if isinstance(d, dict) else d
        overlap = set(d) & set(proposed)
        if overlap:
            print(f"  !! {len(overlap)} name(s) proposed twice, later file wins: "
                  f"{sorted(overlap)[:3]}")
        proposed.update({k: v for k, v in d.items() if isinstance(v, str)})

    missing = [n for n in proposed if n not in paths]
    known = {n: v for n, v in proposed.items() if n in paths}
    print(f"proposed: {len(proposed)}   resolvable to a file: {len(known)}"
          f"{f'   unknown agent names skipped: {len(missing)}' if missing else ''}")
    if missing:
        print(f"  unknown: {sorted(missing)[:5]}")

    if args.dry_run:
        print("(dry run — nothing written)")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(args.backup_root or f"eval/proposals/backup-agents-{stamp}")
    backup.mkdir(parents=True, exist_ok=True)

    applied, skipped = 0, []
    for name, desc in sorted(known.items()):
        src = Path(paths[name])
        try:
            text = src.read_text()
        except OSError as exc:
            skipped.append((name, f"unreadable: {exc}")); continue
        out = replace_description(text, desc)
        if out is None:
            skipped.append((name, "no parseable frontmatter")); continue
        shutil.copy2(src, backup / f"{src.parent.name}__{src.name}")
        src.write_text(out)
        applied += 1

    print(f"applied {applied}   skipped {len(skipped)}")
    for n, why in skipped:
        print(f"  ! {n}: {why}")
    print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
