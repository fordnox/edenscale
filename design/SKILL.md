---
name: edenscale-design
description: Use this skill to generate well-branded interfaces and assets for EdenScale, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

# EdenScale design skill

Read the `README.md` file within this skill, and explore the other available files. The README is the source of truth for brand voice, visual foundations, and content rules.

## What's in this skill

- `README.md` — brand context, content fundamentals, visual foundations, iconography
- `colors_and_type.css` — design tokens (colors, type, spacing, motion) + semantic CSS classes
- `fonts/` — self-hosted webfonts (Cormorant Garamond, Inter Tight)
- `assets/` — logo mark and wordmark SVGs (use `currentColor` to retint)
- `preview/` — example cards demonstrating each token slice; useful as reference
- `ui_kits/website/` — React/JSX components for marketing-website surfaces

## How to use

If creating visual artifacts (slides, mocks, throwaway prototypes), copy assets out and create static HTML files for the user to view. Always link `colors_and_type.css` and reuse the existing components in `ui_kits/` rather than rebuilding from scratch.

If working on production code, copy the tokens and read the rules in `README.md` to become an expert in designing with this brand.

## When invoked without further guidance

Ask the user:
1. What surface are they designing — marketing page, LP portal, deck, email, document?
2. What's the page or component goal in one sentence?
3. Do they want options/variations? On what axis (visual, copy, layout)?

Then act as an expert designer who outputs HTML artifacts *or* production code, depending on the need. Default to:
- Cormorant Garamond for display, Inter Tight for everything else
- Conifer-700 brand color, parchment-50 backgrounds, ink-900 text
- Hairline rules over shadows, square corners over rounded, no gradients
- Lucide icons at 1.5px stroke
- Sentence case, no emoji, no exclamation marks
