// Cortex Command — minimal, hand-rolled markdown → React nodes.
//
// Deliberately tiny (no markdown library, per the build spec). Supports exactly
// what streaming assistant text needs: fenced code blocks, inline code, bold,
// unordered + ordered lists, and paragraphs. Unknown syntax renders verbatim.
// Written to be tolerant of partial input mid-stream (an unclosed ``` fence is
// treated as an open code block).

import type { ReactNode } from "react";

// ---- inline: `code` and **bold** ---------------------------------------- //

const INLINE_RE = /(`[^`]+`|\*\*[^*]+\*\*)/g;

/** Render inline spans (inline code + bold) within a line of text. */
export function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  INLINE_RE.lastIndex = 0;
  let i = 0;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      out.push(
        <code key={keyBase + ":c" + i} className="md-code">
          {tok.slice(1, -1)}
        </code>,
      );
    } else {
      out.push(<strong key={keyBase + ":b" + i}>{tok.slice(2, -2)}</strong>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// ---- block parse -------------------------------------------------------- //

type Block =
  | { t: "p"; lines: string[] }
  | { t: "code"; lang: string; lines: string[] }
  | { t: "ul"; items: string[] }
  | { t: "ol"; items: string[] };

function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  const isBullet = (l: string) => /^\s*[-*]\s+/.test(l);
  const isOrdered = (l: string) => /^\s*\d+\.\s+/.test(l);

  while (i < lines.length) {
    const line = lines[i]!;

    // fenced code block
    const fence = line.match(/^\s*```(.*)$/);
    if (fence) {
      const lang = (fence[1] || "").trim();
      const body: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i]!)) {
        body.push(lines[i]!);
        i++;
      }
      i++; // consume closing fence (or run off the end if unclosed)
      blocks.push({ t: "code", lang, lines: body });
      continue;
    }

    if (line.trim() === "") {
      i++;
      continue;
    }

    if (isBullet(line)) {
      const items: string[] = [];
      while (i < lines.length && isBullet(lines[i]!)) {
        items.push(lines[i]!.replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      blocks.push({ t: "ul", items });
      continue;
    }

    if (isOrdered(line)) {
      const items: string[] = [];
      while (i < lines.length && isOrdered(lines[i]!)) {
        items.push(lines[i]!.replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ t: "ol", items });
      continue;
    }

    // paragraph: consume until blank / list / fence
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i]!.trim() !== "" &&
      !isBullet(lines[i]!) &&
      !isOrdered(lines[i]!) &&
      !/^\s*```/.test(lines[i]!)
    ) {
      para.push(lines[i]!);
      i++;
    }
    blocks.push({ t: "p", lines: para });
  }

  return blocks;
}

/** Render a markdown string to React nodes. Safe for partial/streaming text. */
export function renderMarkdown(src: string): ReactNode {
  const blocks = parseBlocks(src);
  return blocks.map((b, idx) => {
    const key = "b" + idx;
    if (b.t === "code") {
      return (
        <pre key={key} className="codeblock md-pre">
          {b.lines.join("\n")}
        </pre>
      );
    }
    if (b.t === "ul") {
      return (
        <ul key={key} className="md-list">
          {b.items.map((it, j) => (
            <li key={j}>{renderInline(it, key + ":" + j)}</li>
          ))}
        </ul>
      );
    }
    if (b.t === "ol") {
      return (
        <ol key={key} className="md-list">
          {b.items.map((it, j) => (
            <li key={j}>{renderInline(it, key + ":" + j)}</li>
          ))}
        </ol>
      );
    }
    // paragraph — join wrapped lines with spaces, preserve inline formatting
    return (
      <p key={key} className="md-p">
        {renderInline(b.lines.join(" "), key)}
      </p>
    );
  });
}
