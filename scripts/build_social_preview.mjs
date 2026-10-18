#!/usr/bin/env node
// Export the share card with sharp 0.35.5. See docs/maintainers/social-preview.md.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
let sharp;
try {
  sharp = require(process.env.CORTEX_SHARP_MODULE || 'sharp');
} catch {
  console.error('This optional asset export requires sharp 0.35.5. Set CORTEX_SHARP_MODULE to its module path; see docs/maintainers/social-preview.md.');
  process.exit(1);
}
if (sharp.versions.sharp !== '0.35.5') {
  console.error(`Expected sharp 0.35.5; found ${sharp.versions.sharp}. Use the documented renderer for reproducible exports.`);
  process.exit(1);
}
const lockup = readFileSync(resolve(root, 'assets/cortex-logo-light.svg'), 'utf8');
const lockupViewBox = lockup.match(/viewBox="([^"]+)"/)[1];
const lockupBody = lockup.replace(/^[\s\S]*?<svg\b[^>]*>/, '').replace(/<\/svg>\s*$/, '');
// The existing lockup's visible content spans y=23..345 in its 480×420
// viewBox. This placement centers that artwork, preserving its own clearspace.
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640" role="img" aria-label="Cortex">
  <rect width="1280" height="640" fill="#121018"/>
  <svg x="340" y="90" width="600" height="525" viewBox="${lockupViewBox}">${lockupBody}</svg>
</svg>
`;
const png = await sharp(Buffer.from(svg)).png({ compressionLevel: 9, adaptiveFiltering: false }).toBuffer();
const metadata = await sharp(png).metadata();
if (metadata.width !== 1280 || metadata.height !== 640 || png.length >= 1_000_000) {
  throw new Error('Share card must be 1280 × 640 pixels and smaller than 1 MB.');
}
const outputs = [['assets/cortex-social-preview.svg', Buffer.from(svg)], ['assets/cortex-social-preview.png', png]];
let stale = false;
for (const [name, content] of outputs) {
  const path = resolve(root, name);
  if (process.argv.includes('--check')) {
    let previous = Buffer.alloc(0);
    try { previous = readFileSync(path); } catch {}
    if (!previous.equals(content)) { console.error(`Out of date: ${name}`); stale = true; }
  } else {
    writeFileSync(path, content);
    console.log(`Built ${name} (${content.length.toLocaleString('en-US')} bytes)`);
  }
}
if (stale) process.exitCode = 1;
else if (process.argv.includes('--check')) console.log(`Social preview is current: 1280 × 640, ${png.length.toLocaleString('en-US')} bytes.`);
