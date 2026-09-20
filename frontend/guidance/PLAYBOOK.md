# The Non-Vibe-Coded Frontend Design Playbook

## What "non-vibe-coded" means

Vibe coding becomes a problem when the interface is assembled from plausible defaults without a clear reason for its choices. It may function, but it feels interchangeable. The page could belong to any startup, the copy says nothing specific, and visual effects substitute for hierarchy.

A non-vibe-coded interface has evidence of judgment:

- The visual language comes from the subject matter and audience.
- The hierarchy reflects actual user priorities.
- Color, type, space, imagery, and motion have named jobs.
- Repeated patterns use a system, while memorable moments are intentionally unique.
- The interface works beyond the ideal screenshot.
- Accessibility, responsiveness, performance, and error states are part of the design.

The goal is not to hide the use of AI. The goal is to remove unexamined defaults.

## 1. Begin with design context

Do not choose colors, fonts, or components until you can answer:

- Who uses this product?
- What are they trying to accomplish?
- What situation are they in when they use it?
- What should the experience make them feel?
- What three words describe the brand personality?
- What must the design communicate in its first two seconds?
- What must it never resemble?
- What technical, accessibility, performance, or brand constraints are fixed?

Write the answers into the project, ideally in `AGENTS.md`, `CLAUDE.md`, or a dedicated design brief. Persistent context prevents the design from drifting between sessions.

### Use references and anti-references

Ask for two or three references and identify the precise quality that matters. "Like Linear" is weak. "The density and keyboard-first interaction of Linear, but not its dark palette" is useful.

Anti-references are equally valuable. State what the result must avoid. Examples include glossy SaaS cards, editorial layouts, playful motion, dense dashboards, or luxury minimalism. An anti-reference closes common escape routes into generic output.

## 2. Choose a strong visual direction

Write a one-paragraph creative concept before opening the component library. It should connect the product's world to a design idea.

A strong direction contains:

- Purpose: the user problem and primary action.
- Tone: a specific aesthetic and emotional register.
- Materials: visual cues from the subject's real world.
- Constraints: stack, browser support, accessibility, and performance.
- Signature: the one moment or element people should remember.

### Spend boldness in one place

The memorable element may be a typographic hero, interactive diagram, unusual navigation model, full-bleed photograph, spatial composition, or carefully staged animation. Pick one. Keep the surrounding system disciplined enough to let it land.

### Run the interchangeability test

Replace the product name and copy with another company's. If the page still feels equally appropriate, the direction is too generic.

### Common generated-design tells

Treat these as choices that require justification, not defaults:

- Purple-to-blue gradients and cyan accents on dark backgrounds.
- Gradient text used as automatic emphasis.
- Warm cream, high-contrast serif, and terracotta used without a subject-specific reason.
- Acid green on near-black used as instant "edgy" branding.
- Identical rounded cards with soft shadows.
- A large icon in a rounded square above every heading.
- All-caps eyebrow labels above every section.
- Monospace labels added to make an interface feel technical.
- Every section centered and every feature given the same weight.
- Decorative sparklines, glass panels, glow borders, and floating blobs.
- Repeated fade-and-slide entrances on every section.
- Fake metrics or testimonials written only to occupy a template.

None of these devices is forbidden. The test is whether the brief demands them.

## 3. Make a compact design system first

Create a token sheet before styling individual components. A useful minimum system includes:

- Four to six named core colors.
- Semantic colors for success, warning, error, and information.
- One or two type families with assigned roles.
- Five useful type sizes with clear contrast.
- A 4-point spacing scale.
- Two or three radii, not one radius on everything.
- A small elevation system.
- Motion durations and easing curves.
- Container widths and content measures.

Use semantic names such as `surface-raised`, `text-muted`, `action-primary`, and `space-section`. Avoid value-based names that expose implementation details.

### Primitive and semantic layers

Keep raw values separate from their jobs. A primitive may be `blue-600`; a semantic token may be `action-primary`. Dark mode and future themes should mainly redefine semantic tokens.

## 4. Typography carries personality

Typography usually contributes more personality than decoration.

### Selection

- Choose one strong family before adding a second.
- Use a second family only when it adds meaningful contrast.
- Avoid pairing two similar geometric sans-serif families.
- Use display faces for short, controlled text, never long body copy.
- Load only the weights and character sets you actually use.
- Provide metric-compatible fallbacks to reduce layout shift.

Common default fonts are not inherently bad, but they do not provide differentiation by themselves. If the product needs identity, make a deliberate choice.

### Scale and hierarchy

- Use fewer sizes with bigger differences.
- Use a modular relationship rather than a cloud of adjacent values.
- Keep body text at least 1rem and respect browser zoom.
- Use `clamp()` for large display type and fluid editorial text.
- Keep most prose below about 65 to 75 characters per line.
- Increase line-height slightly for light text on dark surfaces.
- Use tabular numerals for aligned data.

Avoid accenting one arbitrary word in every heading. Make the whole typographic composition carry the emphasis.

## 5. Use color as a system

Color should communicate hierarchy, state, category, or brand emotion.

### Palette rules

- Prefer OKLCH for perceptually consistent scales.
- Tint neutrals toward the brand hue.
- Let one accent remain rare enough to feel important.
- Reduce chroma as colors approach white or black.
- Define explicit surface colors instead of stacking transparency everywhere.
- Design dark mode separately. Depth in dark mode usually comes from lighter surfaces, not heavier shadows.

### Accessibility rules

- Body text should meet at least 4.5:1 contrast.
- Large text and essential UI graphics should meet at least 3:1.
- Placeholder text is still text and must remain readable.
- Do not use color as the only indicator of state.
- Test color-blindness simulations and high-contrast modes.

Avoid gray text on colored backgrounds. Use a darker or lighter relative of the background hue.

## 6. Build spatial rhythm, not uniform padding

Use a 4-point base scale with intentional jumps, such as 4, 8, 12, 16, 24, 32, 48, 64, and 96 pixels.

### Hierarchy through space

- Keep related items close.
- Separate conceptual groups generously.
- Combine size, weight, color, position, and space to create hierarchy.
- Use asymmetry when it reinforces the reading order.
- Break the grid only where the break creates emphasis.
- Use `gap` for sibling spacing and reserve margins for larger structural relationships.

### Cards are not layout

Use cards when items are independent, comparable, actionable, or movable. Do not use a card merely because content needs spacing. Avoid nesting cards inside cards. Typography, alignment, dividers, and whitespace often create stronger grouping.

### The squint test

Blur or shrink a screenshot. You should still see the primary element, secondary element, and major groups. If every block has equal weight, the hierarchy is unfinished.

## 7. Treat words as interface components

Copy is not filler.

- Use the user's vocabulary, not internal system terms.
- Use active voice and sentence case.
- Name actions with a clear verb and object.
- Keep action names consistent through the whole flow.
- Remove introductions that repeat their heading.
- Write empty states that explain value and offer a next action.
- Write errors that say what happened and how to recover.
- Do not use jokes when the user is blocked or has lost work.
- Write link text that makes sense out of context.
- Allow 30 to 40 percent expansion for translation.

"Save changes" is better than "Submit." "Delete 5 files" is better than "Yes."

## 8. Design all interaction states

Every interactive component needs a defined default, hover, focus, active, disabled, loading, error, and success state.

### Interaction principles

- Use native HTML controls whenever they can do the job.
- Keep keyboard focus visible with `:focus-visible`.
- Make touch targets at least 44 by 44 CSS pixels when practical.
- Never rely on hover for essential information or actions.
- Validate forms after a field is left, not on every keystroke, unless live validation is genuinely helpful.
- Connect errors to their fields programmatically.
- Prefer skeletons that preview content shape over anonymous spinners.
- Use optimistic updates for reversible, low-risk actions.
- Prefer undo over confirmation for recoverable deletion.
- Use native `dialog`, popover, `details`, and semantic elements where appropriate.

If a gesture exists, provide a visible alternative. Invisible interactions are not discoverable.

## 9. Use motion to explain change

Motion should provide feedback, maintain spatial continuity, direct attention, or create one signature moment.

### A practical timing system

- 100 to 150ms for direct feedback.
- 200 to 300ms for menus, tooltips, and small state changes.
- 300 to 500ms for drawers, dialogs, and layout changes.
- 500 to 800ms for a deliberate entrance sequence.
- Make exits shorter than entrances.

Use decelerating curves for entrances and accelerating curves for exits. Avoid bounce and elastic easing by default. Springy motion can work for a playful brand when the interaction and physical metaphor clearly support it.

Prefer transforms and opacity. Avoid animating width, height, padding, and margin. For collapsible content, use grid row transitions or a purpose-built layout animation system.

### One orchestrated moment

A single page-load composition, scroll-linked story, or product interaction is more memorable than motion sprinkled across every card. Cap stagger sequences so the user never waits for the interface.

Always respect `prefers-reduced-motion`. Preserve state feedback even when spatial movement is removed.

## 10. Adapt, do not merely shrink

Responsive design changes composition and interaction according to available space and input method.

- Start mobile-first and add complexity with `min-width` queries.
- Let content determine breakpoints.
- Use container queries for reusable components.
- Use `clamp()` for fluid space and display type.
- Query pointer and hover capability, not only viewport size.
- Support safe-area insets on modern phones.
- Provide responsive images with `srcset`, `sizes`, and art-directed `picture` sources when necessary.
- Preserve critical functionality on mobile.
- Test 320px, 768px, 1024px, and wide desktop layouts as a minimum sweep.
- Test on real touch hardware and at 200 percent zoom.

## 11. Use component libraries as raw material

Accessible primitives save time. They do not supply art direction.

Use libraries such as shadcn/ui for behavior and structure, icon libraries for consistent geometry, and animation libraries for complex choreography. Then restyle, simplify, and compose them according to the brief.

Do not combine components merely because they look impressive in isolation. A copied background effect, moving border, 3D card, and typewriter headline rarely form a coherent identity together.

### A useful rule

Borrow behavior. Design the surface.

## 12. Add 3D only when it earns its cost

3D is valuable for product visualization, spatial explanation, configuration, education, and genuinely immersive storytelling.

Ask whether a photograph, illustration, or video would communicate the idea more clearly. If not, choose the lightest suitable stack:

- Spline for quick visual authoring and embeds.
- React Three Fiber for React-native scene composition.
- Three.js for maximum control.
- Babylon.js for heavier game-like applications.

Keep web models compact, prefer GLB or glTF, reduce geometry and material count, compress textures, lazy-load the scene, show progress, and provide a static fallback. Test battery, heat, memory, and low-end mobile performance.

Random floating geometry is not a concept.

## 13. Keep implementation disciplined

Visual quality collapses when the code is fragile.

- Use semantic HTML before ARIA.
- Keep component APIs small and composable.
- Use tokens instead of one-off values.
- Avoid deep wrapper trees and specificity fights.
- Reserve image dimensions to prevent layout shift.
- Lazy-load below-the-fold media and heavy experiences.
- Split large routes and components.
- Keep animation work off layout properties.
- Preserve visible loading, empty, error, offline, and permission states.
- Test long content, short content, no content, large numbers, RTL, CJK, slow networks, and failed requests.

## 14. Refine with focused passes

Do not ask an AI tool to "make it better." Run narrow passes with a named purpose.

### Distill

Remove redundant copy, competing actions, decorative containers, unnecessary variants, and extra steps. Preserve the user's primary goal.

### Bolder

Increase contrast in scale, composition, type, or color. Choose one focal point and push it. Do not add generic effects.

### Quieter

Reduce saturation, visual weight, decoration, and motion while preserving hierarchy and identity.

### Colorize

Add color for meaning, wayfinding, hierarchy, or warmth. Define where each color is allowed to appear.

### Animate

Add feedback and spatial continuity. Choose one signature moment and a small motion token system.

### Delight

Add one context-specific surprise, helpful flourish, or rewarding response. Delight should never slow down the main task.

### Normalize

Replace one-off styling and components with the design system's tokens, patterns, and accessible primitives.

### Adapt

Rethink the layout and interaction for mobile, touch, tablet, wide desktop, print, or email.

### Harden and optimize

Test production data, failures, translation, assistive technology, and slow devices. Measure performance before and after.

## 15. Review screenshots, not intentions

Run two separate reviews.

### Design critique

Evaluate:

- First impression and clarity in two seconds.
- Primary task and interaction affordances.
- Reading order and visual hierarchy.
- Consistency with the token system.
- Typography, spacing, color, and content.
- Whether the design feels specific to the brief.

### Production audit

Evaluate:

- Keyboard navigation and focus.
- Screen-reader names and semantic structure.
- Contrast, zoom, and reduced motion.
- Loading, empty, error, offline, and permission states.
- Responsive layouts and real devices.
- Core Web Vitals, bundle cost, image cost, and runtime smoothness.
- Critical E2E flows in Chromium, Firefox, WebKit, and a mobile profile.

When LCP is slow, separate server response time, resource discovery delay, resource transfer time, and element render delay before changing code. A preload will not solve a slow server, and image compression will not solve delayed client rendering.

Take screenshots at representative widths. Compare against references when fidelity matters. Iterate until the major differences are intentional.

## The final standard

The interface is ready when:

- Its concept can be explained in one sentence.
- The first screen communicates the right thing.
- One detail is memorable and the rest is disciplined.
- Components share a coherent system without looking mechanically repeated.
- The copy is specific and useful.
- The important states are designed and implemented.
- It works with keyboard, touch, reduced motion, zoom, and slow networks.
- It is tested at mobile and desktop widths.
- A screenshot review finds no accidental generic defaults.
- Performance and accessibility have been measured, not guessed.
