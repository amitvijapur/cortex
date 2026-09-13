# UI and Frontend Skill Map

These are the design workflows that informed this kit. The exact commands vary by AI environment, but the sequence and responsibilities transfer to any tool.

## Core direction

| Skill | Use it for | Main contribution |
|---|---|---|
| `frontend-design` and `frontend-design:frontend-design` | New pages, components, and visual redesigns | Brief-specific art direction, distinctive type, color, composition, anti-template checks |
| `teach-impeccable` | One-time project setup | Captures users, product purpose, brand personality, references, anti-references, and constraints as persistent design context |
| `anthropic-skills:ui-ux-pro-max` | Early research and stack guidance | Searchable recommendations for product types, styles, palettes, font pairings, charts, UX rules, and framework-specific implementation |
| `design:design-system` | Auditing, documenting, or extending a system | Tokens, component variants, states, patterns, naming, accessibility, and migration discipline |
| `normalize` | Bringing a feature back into the system | Replaces one-offs with shared tokens, components, motion, and interaction patterns |
| `design:design-handoff` | Converting design intent into a buildable specification | Documents tokens, states, responsive behavior, motion, edge cases, and accessibility for implementation |
| `design:ux-copy` | Interface language and content states | Clear actions, errors, empty states, confirmations, loading language, terminology, and localization |
| `coding-standards` | Keeping the implementation maintainable | Type safety, small components, clear state, lazy loading, error handling, testing, KISS, DRY, and YAGNI |

## Focused aesthetic passes

| Skill | Use it when | Guardrail |
|---|---|---|
| `distill` | The page is cluttered or over-explained | Remove obstacles, not necessary capability |
| `bolder` | The work is safe, flat, or forgettable | Increase contrast and commitment, not the number of effects |
| `quieter` | The design is loud or visually tiring | Preserve identity and hierarchy while reducing intensity |
| `colorize` | The design is cold, gray, or lacks hierarchy | Give every color a semantic or emotional job |
| `animate` | State changes are abrupt or feedback is missing | Motion must explain, respond, or create one signature moment |
| `delight` | The experience is correct but joyless | Add context-specific pleasure without blocking the task |
| `adapt` | The design only works in its original context | Rethink composition and input for mobile, touch, tablet, print, or email |
| `polish` | The feature works but details are inconsistent | Fix typography, alignment, states, responsive details, and small visual defects |

## Critique and quality

| Skill | Use it for | Output |
|---|---|---|
| `critique` or `design-critique` | Structured design feedback | Prioritized findings across usability, hierarchy, consistency, and accessibility |
| `audit` | Broad interface quality review | Severity-ranked issues across accessibility, performance, responsiveness, and visual consistency |
| `accessibility:accessibility` or `design:accessibility-review` | WCAG-focused inspection | Keyboard, screen reader, contrast, focus, labels, forms, motion, and target-size findings |
| `visual-verdict` | Comparing a build to a reference image | A repeatable score, concrete differences, and the next visual edits |
| `optimize` or `web-perf` | Loading and runtime performance | Core Web Vitals, bundle, image, font, rendering, and animation improvements |
| `harden` | Real-world resilience | Long text, empty states, failures, internationalization, RTL, slow networks, and edge cases |
| `e2e-testing` | Critical user flows | Cross-browser Playwright tests, screenshots, traces, and failure artifacts |
| `chrome-devtools-mcp:chrome-devtools` | Browser-grounded diagnosis | Screenshots, accessibility tree, console, network, runtime inspection, and performance traces |
| `chrome-devtools-mcp:a11y-debugging` | Reproducing accessibility failures in the browser | Lighthouse, keyboard traversal, DOM order, tap targets, accessible names, and contrast inspection |
| `chrome-devtools-mcp:debug-optimize-lcp` | Improving the real Largest Contentful Paint bottleneck | Separates server, resource delay, transfer, and render delay before choosing a fix |

## Advanced visual implementation

| Skill | Best for | Use carefully because |
|---|---|---|
| `gsap` | Timelines, scroll choreography, pinning, complex sequencing | Animation can dominate content and add runtime cost |
| `aceternity-ui` | React and Tailwind animation patterns and marketing-page components | Combining showcase components without a concept creates a templated result |
| `3d-web-experience` | Three.js, React Three Fiber, Spline, and product visualization | 3D adds load time, battery use, accessibility concerns, and mobile risk |
| `anthropic-skills:frontend-slides` | Interactive web-based presentations | Slide conventions should not leak into product UI without reason |

## Recommended sequence

### For a new marketing website

1. `teach-impeccable`
2. `frontend-design`
3. `anthropic-skills:ui-ux-pro-max` for targeted research
4. Build the token system and functional page
5. One or two of `bolder`, `quieter`, `colorize`, `animate`, or `delight`
6. `adapt`
7. `critique`
8. `design:accessibility-review`, `optimize`, and `harden`

### For an existing product interface

1. `critique`
2. `design-system audit`
3. `normalize`
4. `distill` or `adapt`
5. `polish`
6. `design:accessibility-review`, `harden`, `optimize`, and E2E tests

### For a reference-faithful rebuild

1. Define the reference and content requirements
2. Build the functional version
3. Capture screenshots at fixed widths
4. Run `visual-verdict`
5. Fix the largest differences first
6. Repeat until differences are intentional or the score clears the agreed threshold

## The principle behind the map

Do not stack every skill on every job. Select the smallest set that addresses the actual weakness. A design that needs restraint will not improve because it received more motion, more components, and more color.
