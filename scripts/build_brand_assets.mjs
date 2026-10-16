#!/usr/bin/env node
// Rebuild self-contained README lockups from the mark and supplied lettering.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const png = readFileSync(resolve(root, 'assets/cortex-wordmark-source.png'));
const mark = readFileSync(resolve(root, 'assets/cortex-mark.svg'), 'utf8');
const markViewBox = mark.match(/viewBox="([^"]+)"/)[1];
const markBody = mark.replace(/^[\s\S]*?<svg\b[^>]*>/, '').replace(/<\/svg>\s*$/, '');
const image = `data:image/png;base64,${png.toString('base64')}`;
const variants = [['', '#17121F'], ['-light', '#F1EDF8']];
const check = process.argv.includes('--check');
let stale = false;

for (const [suffix, color] of variants) {
  const rgb = color.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16) / 255);
  const filter = `<filter id="ink" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="0 0 0 0 ${rgb[0]} 0 0 0 0 ${rgb[1]} 0 0 0 0 ${rgb[2]} 0 0 0 1 0"/></filter>`;
  const output = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 420" role="img" aria-labelledby="lockup-title lockup-desc">
<title id="lockup-title">Cortex</title>
<desc id="lockup-desc">Five identical violet arms sweep around a shared centre, above the Cortex wordmark.</desc>
<defs>${filter}</defs>
<svg x="140" y="16" width="200" height="200" viewBox="${markViewBox}">${markBody}</svg>
<image x="70" y="250" width="340" height="114" href="${image}" filter="url(#ink)"/>
</svg>
`;
  const path = resolve(root, `assets/cortex-logo${suffix}.svg`);
  if (check) {
    let existing = '';
    try { existing = readFileSync(path, 'utf8'); } catch {}
    if (existing !== output) { console.error(`Out of date: ${path}`); stale = true; }
  } else {
    writeFileSync(path, output);
    console.log(`Built assets/cortex-logo${suffix}.svg`);
  }
}
if (stale) process.exitCode = 1;
