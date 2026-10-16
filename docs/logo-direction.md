# Cortex logo direction

The current identity is a flat violet mark, with five equal curved arms around
a shared circular opening. `assets/cortex-mark.svg` defines one canonical arm
and repeats it at 72-degree intervals, keeping every arm identical. Cortex remains
the name; synchrony informs the coordinated movement in the mark.

The README uses `assets/cortex-logo.svg` on light backgrounds and
`assets/cortex-logo-light.svg` on dark backgrounds. Both place the supplied Cortex
lettering below the mark. The wordmark source is a transparent PNG reproduced
from the user's reference using the built-in image-generation tool, rather than
an identified or bundled font. The SVG mark is vector geometry; the wordmark is
an embedded raster, so these lockups are mixed-format SVGs. Both modes use the same
lettering source with a flat colour filter, keeping their spacing identical.

`assets/cortex-hero.svg` replaces the raster hero in the README. The documentation
diagrams use the same violet/lavender palette, retaining their explanations and
semantic status colours. The previous blue PNGs remain historical assets.

## Palette and maintenance

| Role | Colour |
| --- | --- |
| Mark and primary accent | `#8B5CF6` |
| Secondary accent | `#C4B5FD` |
| Dark surface | `#121018` |
| Raised dark surface | `#1A1526` |
| Light text | `#F1EDF8` |
| Secondary text | `#B7ACC9` |
| Dark lettering | `#17121F` |

After editing the mark or lettering source, run `node scripts/build_brand_assets.mjs`
to regenerate the two self-contained lockups. `--check` detects stale lockups.
The hero carries the same arm geometry; keep it in sync when changing the mark.
Preview all assets together in `assets/brand-preview.html` at wide and narrow sizes.

The wordmark extraction prompt asked the image tool to preserve the supplied
letter silhouettes, weight, kerning and capitalisation, remove the pale background,
and produce flat dark lettering with transparency. A native SVG filter derives
the light variant from that same source, avoiding separate generated letterforms.

## Previous blue exploration

The prompts below record the earlier dimensional blue concept. They do not define
the current minimal violet identity.

## Initial edit prompt

Use case: style-transfer, logo-brand refinement.
Asset type: production Cortex logo symbol, square composition, genuinely transparent background.
Image 1 is the edit target: the original Cortex blue five-node hub with a circular central aperture and five unequal radial spokes. Evolve THIS identity, not an unrelated mark.
Primary request: make the original much more sophisticated, futuristic, abstract and memorable, expressing SYNCHRONOUS: distinct agents moving in phase as one coordinated system. Keep the Cortex name unchanged but put NO text in this symbol.
Preserve invariants: five peripheral elements, central circular negative-space aperture, recognizable radial hub ancestry, original electric-blue/deep-navy family.
Transform: replace the five basic round dots and straight sticks with five individually sculpted curved signal vanes, each sweeping coherently around the same central opening. The vanes are linked by flowing tapered channels so they read as one phase-locked system, not five disconnected satellites. Subtle differences in radial reach preserve the original asymmetric character. Make the silhouette compact and distinctive, with intentional clean negative-space cuts and generous substantial forms that survive at 130 pixels. The conceptual reference is an advanced instrument capturing synchronized motion, not a propeller or floral rosette.
Style: precise, premium experimental technological identity. Controlled dimensionality on sculpted surfaces, luminous blue edges and deep navy bodies; restrained tonal depth, no diffuse neon glow or drop shadow. Dynamic tension, continuous coordinated motion, clearly engineered curves with a few crisp terminations. Not a conventional rounded SaaS icon. Not a molecule diagram with decorations.
Composition: one large centered symbol occupying about 78 percent of the square, generous transparent margin. No presentation board, no labels, no background plate, no checkerboard drawn into image. Real transparent alpha outside the mark and through the central aperture.
Avoid: words, initials, infinity signs, chain-link knots, generic AI sparkles, brains, literal clocks, sync arrows, tiny circuit traces, complex wireframe, excessive chrome, bevel overload, exploded parts, three separate options. Render one resolved evolution of the actual supplied logo.

## Finishing edit prompt

Edit the supplied Cortex logo. Preserve its exact five-node radial structure, five unequal peripheral round nodes, clockwise flowing curved connections, central transparent circular aperture and overall silhouette. This is a finishing pass, not a redesign.
Change only the rendering/material and edge quality: replace the glossy glowing cyan plastic with a sophisticated precision-machined graphic treatment. Deep midnight navy surfaces, subtle electric-blue tonal planes, very restrained thin blue seam highlights. Matte/satin, not chrome. Clear graphic separation of the five phase-aligned paths. Keep enough medium blue that the silhouette remains readable on dark and white interfaces. Eliminate the broad luminous cyan bands, all bloom, all outer glow, and all speckled pixels/halos. Crisp immaculate anti-aliased perimeter.
The mark should feel like a futuristic scientific instrument identity, not a toy, game collectible or fidget spinner. Keep all five terminal disks but integrate their fill seamlessly with their flowing paths; no extruded face rims.
One centered square logo, generous margins, genuine transparent background and transparent central hole. No text, no labels, no additional shapes, no shadow, no background panel, no checkerboard. Output intended for the Cortex README at 130px and full-resolution brand use.
