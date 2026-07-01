## NewTaven design system — build conventions

This is a **tokens-only** design system: no packaged React components ship (`_ds_bundle.js` is empty). Everything you build with it is plain HTML/CSS/JSX styled directly from `styles.css` — there is no provider, wrapper, or root component to mount.

**Setup.** Link the one stylesheet; nothing else is required:
```html
<link rel="stylesheet" href="styles.css">
```
`styles.css` imports `fonts/fonts.css` (webfont `@font-face` rules) and `_ds_bundle.css` (all tokens + semantic classes) — read `_ds_bundle.css` directly if you need the full token list.

**Styling idiom.** Two layers, both CSS custom properties (`var(--*)`), never Tailwind-style utility classes:
- **Primitives** — raw palette/scale steps, e.g. `--conifer-50…900` (brand green), `--brass-50…900` (single warm accent — eyebrows, link-hover underlines, small emphases *only*, never buttons or large fields), `--parchment-50…300` / `--ink-300…900` (neutrals), `--sp-0…11` (4px-based spacing), `--fs-*` (type sizes).
- **Semantic aliases** — what you should actually reach for: `--bg-page`, `--bg-surface`, `--bg-inverse`; `--fg-primary`, `--fg-secondary`, `--fg-tertiary`, `--fg-muted`, `--fg-inverse`, `--fg-accent`; `--border-hairline` (default rule) / `--border-default` (section breaks) / `--border-strong`; `--radius-xs` (2px, inputs/buttons only — default radius is **0**, everything else is square); `--shadow-xs…lg` (used sparingly — cards are flat + hairline-bordered, never "lifted" with shadow).
- **Type**: two families — `--font-display` (Cormorant Garamond, medium/500 only, never regular or bold) for headlines/pull-quotes, `--font-sans` (Inter Tight) for everything else, `--font-mono` for small tracked labels. Ready-made classes ship in the CSS — use these instead of hand-rolling font-size/line-height: `.es-display-xl/l/m/s` (hero/section headlines), `.es-h1…h4` (sub-headings, sans), `.es-body-l/.es-body/.es-body-s` (copy), `.es-eyebrow` (uppercase tracked label, brass), `.es-caption`, `.es-quote` (italic pull-quote), `.es-numeric`/`.es-numeric-oldstyle` (tabular vs. oldstyle figures). Apply `.es-page` to `<body>` for the base background/text/font-smoothing reset.
- **Motion**: `--motion-fast` (140ms, hover), `--motion-base` (220ms, page-level), `--ease-standard` (`cubic-bezier(0.4,0,0.2,1)`). No spring/bounce, no hover scale > 1.02, scroll reveals are opacity+8px translate-y once, never repeating.

**Visual rules that aren't in the tokens but matter**: no gradients anywhere except a single bottom-up scrim behind hero text over a photo; no glassmorphism; square corners are the default, rounding is reserved for inputs/buttons (2px) and pill-shaped tags (999px) only; one full-bleed photograph per marketing page, never stock "people in a meeting."

**Voice**: sentence case in body copy (Title Case only in short nav/button labels), plain and evidence-led ("we hold fewer companies" not "best-in-class portfolio"), em-dashes with no spaces, curly quotes, no emoji, no exclamation marks.

**Example** (adapted from a verified page build):
```html
<body class="es-page">
  <span class="es-eyebrow">Approach</span>
  <h1 class="es-display-l" style="color: var(--fg-primary)">Patient capital, deployed deliberately.</h1>
  <p class="es-body-l" style="color: var(--fg-secondary); max-width: 46ch;">
    We invest on a generational horizon — fewer companies, held longer, with the people who built them.
  </p>
  <a href="#" class="es-body" style="border-bottom: 1px solid var(--brass-500); padding-bottom: 2px;">Our approach →</a>
</body>
```
