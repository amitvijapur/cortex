#!/usr/bin/env python3
"""Check published guide links and brand assets offline using only the stdlib.

This is a deliberately small Markdown link checker, not a Markdown renderer.
Fenced code and inline code examples are ignored. External URLs are not fetched.
Historical reports and session logs are not treated as maintained product guides.
Pass specific Markdown files to check a smaller selection (also useful for fixtures).
"""
import argparse
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import struct
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = {"work-log.md", "lessons.md", "review-fixes-evaluation.md",
              "jev-pilot-results.md"}
CANONICAL = ("README.md", "LICENSE", "CONTRIBUTING.md", "CHANGELOG.md",
             "docs/setup.md", "docs/cli.md", "docs/routing.md", "docs/registry.md",
             "docs/history.md", "docs/first-run.md", "docs/maintenance.md",
             "docs/adoption-feedback.md", "examples/minimal-registry.md",
             "docs/maintainers/README.md", "docs/maintainers/social-preview.md",
             "bin/cortex", "install.sh")


def prose(text, inline_code=True):
    """Blank code blocks while preserving line numbers for actionable errors."""
    result, fence = [], None
    for line in text.splitlines():
        opening = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.match(r"^\s{0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$", line):
                fence = None
            result.append("")
        elif opening:
            fence = opening.group(1)
            result.append("")
        else:
            result.append(re.sub(r"(`+).*?\1", "", line) if inline_code else line)
    return "\n".join(result)


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in (("id", "name") if tag == "a" else ("id",)):
            if attrs.get(key):
                self.ids.add(attrs[key])
        for key in ("href", "src"):
            if attrs.get(key):
                self.links.append((self.getpos()[0], attrs[key]))
        if attrs.get("srcset"):
            self.links.extend((self.getpos()[0], item.strip().split()[0])
                              for item in attrs["srcset"].split(",") if item.strip())


def anchors(path):
    text = prose(path.read_text(encoding="utf-8"), inline_code=False)
    parser = HTMLLinks()
    parser.feed(text)
    result, counts = parser.ids, {}
    for line in text.splitlines():
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not heading:
            continue
        title = re.sub(r"<[^>]+>", "", html.unescape(heading.group(1))).lower()
        title = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", title)
        slug = "".join(c for c in title if c.isalnum() or c in "_ -").replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def links(path):
    text = prose(path.read_text(encoding="utf-8"))
    parser = HTMLLinks()
    parser.feed(text)
    found = list(parser.links)
    references = {}
    for number, line in enumerate(text.splitlines(), 1):
        definition = re.match(r'^\s{0,3}\[([^]]+)\]:\s*(<[^>]+>|\S+)', line)
        if definition:
            target = definition.group(2).strip("<>")
            references[definition.group(1).casefold()] = target
            found.append((number, target))
    for number, line in enumerate(text.splitlines(), 1):
        # Support balanced parentheses in common Markdown destinations.
        for match in re.finditer(r'!?\[[^]\n]*\]\(\s*(<[^>]+>|(?:[^\s()]|\([^()]*\))+)(?:\s+"[^"]*")?\s*\)', line):
            found.append((number, match.group(1).strip("<>")))
        for match in re.finditer(r'!?\[([^]\n]+)\]\[([^]\n]*)\]', line):
            key = (match.group(2) or match.group(1)).casefold()
            found.append((number, references.get(key, "missing-reference:" + key)))
    return found


def check_links(paths):
    failures, count = [], 0
    for path in paths:
        for line, target in links(path):
            if target.startswith("missing-reference:"):
                failures.append(f"{path.relative_to(ROOT)}:{line}: undefined {target}")
                continue
            url = urlsplit(html.unescape(target))
            if url.scheme or url.netloc:
                continue
            count += 1
            destination = ((ROOT / unquote(url.path).lstrip("/")) if url.path.startswith("/")
                           else path.parent / unquote(url.path)) if url.path else path
            destination = destination.resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                failures.append(f"{path.relative_to(ROOT)}:{line}: missing local target {target}")
            elif url.fragment and destination.suffix.lower() in (".md", ".html"):
                if unquote(url.fragment) not in anchors(destination):
                    failures.append(f"{path.relative_to(ROOT)}:{line}: missing anchor {target}")
    return failures, count


def check_assets():
    failures = []
    for asset in sorted((ROOT / "assets").glob("*.svg")):
        try:
            if ET.parse(asset).getroot().tag != "{http://www.w3.org/2000/svg}svg":
                raise ValueError("missing SVG root")
        except (ET.ParseError, ValueError) as exc:
            failures.append(f"{asset.relative_to(ROOT)}: invalid SVG: {exc}")
    social = ROOT / "assets/cortex-social-preview.png"
    source = ROOT / "assets/cortex-social-preview.svg"
    if not source.is_file():
        failures.append("missing social preview source: assets/cortex-social-preview.svg")
    if not social.is_file():
        failures.append("missing social preview: assets/cortex-social-preview.png")
    else:
        data = social.read_bytes()
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            failures.append("social preview must be a PNG with an IHDR header")
        elif struct.unpack(">II", data[16:24]) != (1280, 640):
            failures.append("social preview must measure 1280 x 640 pixels")
        if len(data) >= 1_000_000:
            failures.append("social preview must be smaller than 1 MB")
    demo = ROOT / "assets/cortex-demo.gif"
    if demo.exists():
        data = demo.read_bytes()
        if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
            failures.append("assets/cortex-demo.gif: invalid GIF header")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="specific Markdown files; omit to check product docs and assets")
    args = parser.parse_args()
    if args.files:
        paths = [Path(name).resolve() for name in args.files]
    else:
        paths = sorted({*ROOT.glob("*.md"), *(p for p in (ROOT / "docs").rglob("*.md")
                       if p.name not in HISTORICAL and not re.search(r"\d{8}", p.name)),
                       ROOT / "eval/README.md", ROOT / "frontend/README.md"})
    for path in paths:
        if not path.is_relative_to(ROOT) or not path.is_file():
            parser.error(f"not a repository file: {path}")
    failures, count = check_links(paths)
    if not args.files:
        failures.extend(f"missing canonical file: {name}" for name in CANONICAL if not (ROOT / name).is_file())
        failures.extend(check_assets())
    if failures:
        print("Documentation checks failed:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print(f"Documentation checks passed ({len(paths)} guides, {count} local references). External URLs were not fetched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
