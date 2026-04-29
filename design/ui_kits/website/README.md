# EdenScale — Website UI Kit

Marketing-website surface for EdenScale: a private investment group's public presence. The kit covers a header, hero, an "approach" section, a portfolio strip, a quarterly-letter strip, a CTA card, and a footer — composed into a single demonstration page (`index.html`).

## Files

- `index.html` — interactive demo combining all components in order
- `Header.jsx` — top nav with wordmark, nav links, and "Limited partner login" pill
- `Hero.jsx` — full-bleed editorial hero with serif display headline + protection gradient
- `ApproachSection.jsx` — three-column principles block with eyebrow + serif title + body
- `PortfolioStrip.jsx` — table-style holdings list (uses tabular figures and hairline rules)
- `LetterStrip.jsx` — three quarterly letter cards with date metadata
- `CtaCard.jsx` — full-bleed conifer-ground card pulling the reader toward an LP application
- `Footer.jsx` — multi-column footer with disclosure paragraph

All components consume tokens from `../../colors_and_type.css`. They are intentionally cosmetic — focused on hitting the design system pixel-accurately, not on production code.
