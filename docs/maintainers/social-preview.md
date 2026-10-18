# Maintaining the social preview

[`assets/cortex-social-preview.png`](../../assets/cortex-social-preview.png) is the
upload-ready repository share image. It contains only the existing violet mark
above the original Cortex wordmark, centered on a plain `#121018` background.
The canonical light lockup is reused intact, preserving its mark geometry,
lettering pixels, proportions, colours and spacing. There is no tagline, diagram,
URL or decoration. The existing logo, mark and README hero remain unchanged.

The card is 1280 × 640 pixels and smaller than GitHub's 1 MB limit. The visible
artwork is centered with generous clearspace and was inspected at full size and
at a 640 × 320 reduction.

## Updating the image shown beside shared links

Committing this image does **not** update GitHub's repository social preview.
An administrator must separately open the repository's **Settings → General →
Social preview**, choose **Edit → Upload an image**, and select the PNG above.
See [GitHub's social preview instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview).

After upload, inspect the repository page's `og:image` and `twitter:image`
metadata to confirm that GitHub serves the new uploaded image. Also verify the
image visually in repository settings. A public share service may still show an
older cached image, so check a fresh share preview before publishing. Do not
promise immediate cache invalidation or claim a post has been published merely
because GitHub's metadata changed.

## Rebuilding

The layout source is [`scripts/build_social_preview.mjs`](../../scripts/build_social_preview.mjs).
It reads [`assets/cortex-logo-light.svg`](../../assets/cortex-logo-light.svg),
embeds that existing vertical lockup without altering its contents into the
standalone [`assets/cortex-social-preview.svg`](../../assets/cortex-social-preview.svg),
and exports the PNG. Regenerate both outputs together after a canonical lockup
change. Do not redraw the mark or substitute type for the original lettering.

The optional export dependency is **sharp 0.35.5**, with its normal SVG renderer
(libvips/librsvg). The verified build used Node's bundled runtime, libvips 8.18.7
and librsvg 2.63.2 on macOS. The card contains no typeset text, so no font package
is needed. The checked-in PNG works independently of Node, sharp or this export
step. Neither the Cortex CLI nor installation requires this dependency.

If sharp is already resolvable from Node, use:

```bash
node scripts/build_social_preview.mjs
node scripts/build_social_preview.mjs --check
```

Otherwise install the optional renderer in a temporary directory, avoiding any
repository dependency or lockfile changes:

```bash
npm install --prefix /tmp/cortex-social-renderer --no-save --package-lock=false sharp@0.35.5
CORTEX_SHARP_MODULE=/tmp/cortex-social-renderer/node_modules/sharp node scripts/build_social_preview.mjs
CORTEX_SHARP_MODULE=/tmp/cortex-social-renderer/node_modules/sharp node scripts/build_social_preview.mjs --check
```

For Codex's bundled runtime, the exact command used for the checked-in export was:

```bash
CORTEX_SHARP_MODULE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp" \
  "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node" \
  scripts/build_social_preview.mjs
```

Append `--check` to verify the export. Check mode regenerates both outputs in
memory and compares their complete bytes with the checked-in files. It exits
nonzero if either is stale and never writes files. Both modes also enforce the
1280 × 640 dimensions and the size limit. After an intentional renderer change,
inspect the full-size card and the 640 × 320 reduction again.
