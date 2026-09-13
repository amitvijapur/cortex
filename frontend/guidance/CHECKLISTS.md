# Frontend Design Checklists

## Five-minute anti-vibe check

- [ ] The product, user, and primary job are explicit.
- [ ] The visual concept can be explained in one sentence.
- [ ] The hero uses content or behavior specific to the subject.
- [ ] There is one memorable element, not ten effects.
- [ ] Changing the logo would not make the page fit any random startup.
- [ ] Typography, composition, and copy do more work than decoration.
- [ ] Cards exist because the content is independent or interactive.
- [ ] Color has named roles.
- [ ] Motion explains state or rewards an action.
- [ ] Generic filler copy and fake metrics are gone.

## Visual system

- [ ] Primitive and semantic color tokens exist.
- [ ] Tinted neutrals fit the brand temperature.
- [ ] Accent color is rare enough to preserve hierarchy.
- [ ] One or two type families have clear roles.
- [ ] The type scale uses few sizes with meaningful contrast.
- [ ] Body copy has a readable measure and line-height.
- [ ] A 4-point spacing scale is used consistently.
- [ ] Radius and elevation vary by purpose, not habit.
- [ ] Desktop and mobile compositions are both intentional.
- [ ] The squint test reveals a clear first and second priority.

## Components and interaction

- [ ] Default, hover, focus, active, disabled, loading, error, and success states exist where relevant.
- [ ] Native elements are used before custom controls.
- [ ] All interactive elements are keyboard reachable.
- [ ] Focus indicators are visible and not obscured.
- [ ] Touch targets are at least 44 by 44 CSS pixels when practical.
- [ ] Forms have visible labels and specific errors.
- [ ] Empty states explain value and offer a next action.
- [ ] Destructive actions use undo when recovery is possible.
- [ ] Important behavior never depends on hover alone.
- [ ] The same action uses the same name throughout the flow.

## Motion

- [ ] Motion has a functional or narrative purpose.
- [ ] There is no repeated animation simply because a component exists.
- [ ] Direct feedback feels immediate.
- [ ] Exits are shorter than entrances.
- [ ] Stagger sequences do not make users wait.
- [ ] Transform and opacity are preferred over layout properties.
- [ ] Reduced-motion behavior is implemented and checked.
- [ ] Animation stays smooth on a lower-powered device.

## Responsive and content resilience

- [ ] Layout works at 320px, 375px, 768px, 1024px, and 1440px.
- [ ] There is no horizontal scroll.
- [ ] Critical features remain available on mobile.
- [ ] Touch and pointer inputs are both supported.
- [ ] Content works at 200 percent zoom.
- [ ] Long strings wrap, truncate, or expand intentionally.
- [ ] German-length expansion, CJK, emoji, and RTL have been considered.
- [ ] Images use appropriate dimensions, formats, and responsive sources.
- [ ] Safe areas and mobile browser chrome do not cover controls.

## Accessibility

- [ ] The page has a meaningful title and language.
- [ ] Landmarks and headings form a logical structure.
- [ ] Images have useful alt text or empty alt text when decorative.
- [ ] Normal text meets 4.5:1 contrast.
- [ ] Large text and essential UI graphics meet 3:1 contrast.
- [ ] Color is never the only indicator.
- [ ] Dynamic status messages are announced when needed.
- [ ] Dialogs manage focus and restore it on close.
- [ ] Keyboard testing and at least one screen-reader pass are complete.
- [ ] Automated accessibility checks are supplemented by manual checks.

## Performance

- [ ] Largest Contentful Paint content is identified and prioritized.
- [ ] Image and video dimensions reserve layout space.
- [ ] Above-the-fold media is not accidentally lazy-loaded.
- [ ] Below-the-fold heavy media is lazy-loaded.
- [ ] Fonts are subset, limited, and loaded without blocking text.
- [ ] Large routes and components are split where useful.
- [ ] Unused libraries and third-party scripts are removed.
- [ ] Runtime animation avoids layout thrashing.
- [ ] LCP, INP, and CLS are measured on a realistic profile.
- [ ] LCP is at or below 2.5 seconds at the 75th percentile, or its remaining gap is documented.
- [ ] Performance is compared before and after optimization.

## Production resilience

- [ ] Loading, empty, partial, success, error, offline, and permission states work.
- [ ] User input survives recoverable failures.
- [ ] Duplicate submissions and race conditions are handled.
- [ ] Dates, numbers, currency, and pluralization use locale-aware APIs.
- [ ] Client-side validation is backed by server-side validation.
- [ ] Critical flows have E2E coverage.
- [ ] E2E failures retain screenshots, traces, or video.
- [ ] Chromium, Firefox, WebKit, and a mobile profile are covered as appropriate.

## Final critique

- [ ] Screenshot review was performed at mobile and desktop widths.
- [ ] The three highest-impact visual issues were fixed.
- [ ] Repeated elements share a system without feeling mechanically cloned.
- [ ] Decorative elements that do not support the concept were removed.
- [ ] Copy is concrete, concise, and consistent.
- [ ] The interface remains specific to the product after polish.
- [ ] Known limitations are documented.
- [ ] The final recommendation is explicitly ship or revise.
