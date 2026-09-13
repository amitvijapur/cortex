# Frontend Design Prompt Pack

Replace bracketed text before use. These prompts are designed to work with most coding agents.

## 1. Design context interview

```text
Before designing, inspect the existing project for product purpose, users, brand assets, design tokens, components, and technical constraints.

Then ask only the questions you cannot answer from the project:
- Who is the primary user and what job are they trying to complete?
- What should the interface make them feel?
- What three words describe the brand personality?
- Which references capture the right quality, and what exactly should be borrowed from each?
- What should the design explicitly avoid?
- Which accessibility, performance, browser, or brand requirements are fixed?

Write the answers into a short persistent Design Context section with Users, Brand Personality, Aesthetic Direction, Constraints, Anti-References, and 3 to 5 Design Principles.
```

## 2. Master design and build prompt

```text
Design and implement [PAGE OR FEATURE] for [PRODUCT]. The primary user is [USER], and their main goal is [GOAL]. The brand should feel [THREE ADJECTIVES].

Start with a compact design plan before coding. Include:
1. A one-sentence concept grounded in the product's subject matter.
2. The one memorable visual or interactive idea.
3. A palette of 4 to 6 named colors with exact values and semantic roles.
4. One or two typefaces with clear roles, a small type scale, and loading strategy.
5. A spacing scale, container strategy, radii, elevation, and motion tokens.
6. A short ASCII wireframe for desktop and mobile.
7. The empty, loading, error, success, and disabled states that matter.

Review the plan against the brief. Replace any choice that could belong unchanged to a generic SaaS template.

Then implement a functional, responsive, accessible version. Use semantic HTML, visible keyboard focus, reduced-motion support, appropriate touch targets, responsive images, and content-specific copy. Use shared tokens and components instead of one-off values.

Avoid default AI styling unless the brief explicitly calls for it. This includes purple-to-blue gradients, cyan glows on dark backgrounds, gradient headline text, glass cards, repeated rounded feature cards, decorative sparklines, generic all-caps eyebrow labels, arbitrary monospace labels, and identical fade-up animations on every section.

Finish by taking screenshots at 375px, 768px, and 1440px. Critique hierarchy, typography, spacing, content, responsiveness, and specificity to the brief. Fix the three highest-impact issues before presenting the result.
```

## 3. Art-direction prompt

```text
Propose three genuinely different visual directions for [PRODUCT]. Ground each direction in the product's real materials, culture, workflow, or environment.

For each direction provide:
- Concept and emotional tone
- Signature element
- Color approach
- Typography approach
- Composition and grid behavior
- Image or illustration treatment
- Motion approach
- What makes it specific to this product
- The main risk

Do not produce three variations of the same SaaS landing page. Do not use trends as concepts. Recommend one direction and explain why it best serves the user's main goal.
```

## 4. Anti-generic review

```text
Review this interface for signs of generic AI-generated design. Do not judge whether it is fashionable. Judge whether its choices are specific, coherent, and useful.

Check:
- Could the product name be replaced without changing the design?
- Does the hero use the subject's most characteristic content or a template?
- Are typography and layout carrying personality, or are effects doing the work?
- Are cards, labels, icons, gradients, shadows, and motion used because the content requires them?
- Does every section have the same alignment, weight, radius, and animation?
- Is the copy concrete, or is it generic marketing filler?
- Is there one memorable element and enough restraint around it?

Return the five strongest tells, why each weakens the result, and the smallest high-impact correction for each. Then propose one revised concept sentence.
```

## 5. Distill pass

```text
Simplify [PAGE OR FEATURE] around one primary user goal: [GOAL].

Identify competing actions, repeated copy, unnecessary containers, nested cards, redundant labels, arbitrary variants, and information that can be progressively disclosed. Preserve every capability users need.

Propose the removals first. Then implement the smallest coherent simplification. Verify that the reading order, primary action, keyboard access, and necessary secondary features remain clear.
```

## 6. Bolder pass

```text
This design is too safe. Make it more memorable without adding generic visual effects.

Choose one focal point and increase contrast through no more than two of these dimensions: scale, typography, composition, color, image treatment, or interaction. Keep everything else disciplined. Do not use neon-on-dark, purple-blue gradients, glass cards, gradient text, or random floating shapes.

Explain the visual risk, implement it, then confirm that readability, responsiveness, performance, and the primary task still work.
```

## 7. Quieter pass

```text
This interface is visually tiring. Refine it without making it generic.

Preserve the core idea and strongest point of hierarchy. Reduce competing color, decoration, heavy type, excessive contrast, unnecessary layering, and decorative motion. Use spacing, alignment, and a smaller number of precise accents to signal quality.

List what you are removing or reducing and why, then implement the pass.
```

## 8. Motion pass

```text
Add purposeful motion to [PAGE OR FEATURE]. First identify state changes that lack feedback, spatial relationships that are unclear, and one possible signature moment.

Define motion tokens for direct feedback, small state changes, layout transitions, and entrances. Prefer transforms and opacity. Keep exits shorter than entrances. Avoid bounce and elastic easing. Cap stagger duration.

Implement only motion that explains change, acknowledges input, or creates the one signature moment. Add a reduced-motion alternative and verify keyboard and touch behavior.
```

## 9. Screenshot critique

```text
Critique this screenshot in two passes.

Pass 1, design:
- What attracts attention first, and is that correct?
- Is the page's purpose clear in two seconds?
- Is the reading order clear?
- Are type, space, color, imagery, and copy coherent?
- Which choices feel specific to the product?
- Which choices feel accidental or templated?

Pass 2, production:
- Check mobile adaptation, overflow, focus, contrast, touch targets, reduced motion, loading states, and performance risks.

Rank findings by impact. Recommend at most five changes. Make each recommendation concrete enough to implement.
```

## 10. Production hardening prompt

```text
Harden this interface for real users. Test or reason through:
- No data, one item, many items, and partial data
- Long text, short text, emoji, CJK, and RTL
- 200 percent zoom and keyboard-only navigation
- Slow, offline, timed-out, unauthorized, forbidden, not-found, rate-limited, and server-error states
- Repeated clicks, stale responses, and interrupted navigation
- 320px mobile, tablet, desktop, wide desktop, touch, and pointer input
- Reduced motion and high contrast

Fix issues with minimal code and shared patterns. Do not hide critical functionality on small screens. Report the cases tested and any remaining risks.
```

## 11. Pre-delivery verification prompt

```text
Do a final frontend verification pass. Do not claim completion from code inspection alone.

Run the project's lint, type checks, unit tests, and relevant E2E tests. Inspect screenshots at representative mobile and desktop widths. Check keyboard navigation, visible focus, text and UI contrast, responsive overflow, image dimensions, loading and error states, reduced motion, and Core Web Vitals risks.

Return:
1. Checks run and evidence
2. Issues found and fixed
3. Known limitations
4. A clear ship or revise recommendation
```
