# EdenScale Design System

> A measured, generational visual language for a private investment group.

EdenScale is a private equity & alternative investments group serving a selective community of long-term investors. The design system reflects that audience: deliberate, unhurried, institutional, and quietly distinctive. It speaks the language of stewardship — not growth-hacking.

## Index

| File / Folder | Purpose |
|---|---|
| `README.md` | This file. Brand overview, content + visual foundations, iconography. |
| `colors_and_type.css` | All design tokens (colors, type, spacing, motion) and semantic CSS classes. |
| `SKILL.md` | Agent skill manifest — load into Claude Code or use in this project. |
| `fonts/` | Self-hosted webfonts (Cormorant Garamond, Inter Tight). |
| `assets/` | Logos, marks, and brand visual assets. |
| `preview/` | Cards rendered in the Design System tab — tokens, components, specimens. |
| `ui_kits/website/` | Marketing-website UI kit (React/JSX components + interactive `index.html`). |

---

## Brand context

**EdenScale** is positioned as a private investment group focused on:

- Private equity (control and minority positions in established mid-market businesses)
- Real assets (real estate, infrastructure, natural resources)
- Selective public-market and credit allocations

The audience is **limited partners, family offices, and accredited investors** — sophisticated, time-poor, and skeptical of marketing language. They expect substance over polish.

The name carries two threads we lean into visually:

- **Eden** — cultivated abundance, stewardship, patience, organic growth
- **Scale** — balance, measurement, weight, capital allocation

The wordmark mark literalizes this: a balance scale formed from a stylized stem, with subtle leaf flourishes at the top.

### Sources & references

- **No external design system was provided.** This system was designed from first principles for EdenScale based on the brief: *original design system for a private equity / alternative investments group.*
- The user's GitHub repo `fordnox/KUB-8BC` was attached but was empty (9-byte README), so it provided no codebase context.
- Fonts substituted from Google Fonts (Cormorant Garamond, Inter Tight). **If EdenScale licenses brand-specific typefaces** (e.g. Söhne, Tiempos, GT Sectra, Untitled Sans), please supply them and I will swap.

---

## Content fundamentals

EdenScale's voice is **plain, considered, and quietly confident**. It assumes the reader is intelligent and busy. It avoids superlatives, marketing puffery, and any hint of FOMO.

### Voice principles

| Do | Don't |
|---|---|
| **Specific** — "12-year average hold" | "Long-term focus" |
| **Restrained** — "We invest in fewer companies" | "Best-in-class portfolio companies" |
| **Plain** — "We back operators" | "We empower founders to unlock value" |
| **Evidence-led** — name the thing, cite the number | Adjective stacks |
| **Sentence case** in body, **Title Case** in nav and headings | ALL CAPS shouting (small caps eyebrows are fine) |

### Voice — pronouns

- **"We"** for the firm. Always plural — EdenScale is a group of partners, never a single voice.
- **"You"** for the reader, used sparingly — only in direct contexts (forms, login, an LP portal). Marketing copy mostly stays in the third-person ("Limited partners can…").
- Never "I." Never "us at EdenScale" — just "we."

### Tone — by surface

- **Marketing site / public pages** — declarative, magazine-like. Short paragraphs. One idea per paragraph. Generous whitespace gives the reader room to think.
- **LP portal / data screens** — neutral, near-clinical. Numbers do the talking; chrome stays out of the way.
- **Legal / disclosures** — formal, complete sentences, no contractions ("do not," not "don't"). Required by counsel anyway.

### Tone — examples

> ✅ **"We invest patiently. Most of our holdings are over a decade old."**
>
> ❌ ~~"We're long-term partners on a mission to unlock generational value."~~

> ✅ **"Quarterly letters are sent to limited partners on the fifteenth."**
>
> ❌ ~~"📊 Stay in the loop with our investor updates! 🚀"~~

> ✅ **"Approach"** *(nav label)*
>
> ❌ ~~"Our Investment Philosophy & Approach"~~

### Casing rules

- Headlines and display copy: **sentence case**, except proper nouns and the brand name.
- Navigation, buttons, and metadata labels: **Title Case** for two-word-or-shorter, **sentence case** for longer.
- Eyebrow labels (small caps, tracked): **UPPERCASE** with `letter-spacing: 0.16em`. These are the only place caps shout.
- Numbers: oldstyle figures (`onum`) in display serif copy, lining tabular figures (`tnum lnum`) in any data table.

### Punctuation & details

- Use **em-dashes**, no spaces — like this — for editorial asides.
- Use **proper curly quotes** (`"`, `'`), not straight ones. Same with apostrophes.
- Use the **figure dash** (–) or **en dash** (–) for ranges: "2018–2024," not "2018-2024."
- One space after a period.
- No emoji. No exclamation marks (the only exception is in error toasts: "We weren't able to load that.").

---

## Visual foundations

### Palette

Three colors do almost all the work. Restraint is the point.

- **Conifer green** (`#1F3D2E` / `--conifer-700`) — the brand color. Used on backgrounds for inverse sections, on primary buttons, and as the headline color for emphasis.
- **Parchment cream** (`#FBF9F4` / `--parchment-50`) — the page background. Off-white, warm, slightly aged. Never pure white.
- **Ink** (`#1A1A18` / `--ink-900`) — primary text. Near-black with a green undertone, never `#000`.

A single **brass** accent (`#B8915C`) is reserved for: eyebrow labels, the gold dot on quarterly-update markers, hover-state link underlines, and one or two display-type emphases per page. It is **never** used for buttons or large color fields.

Status colors (positive / negative / info) are intentionally muted and kept inside their natural use cases (gain/loss in tables, form states). They never bleed into marketing pages.

### Typography

A two-family system, deliberately under-curated.

- **Display: Cormorant Garamond** (medium, 500). Used for hero headlines, page titles, pull quotes, and the wordmark. The Garamond proportions feel literary and timeless without slipping into "wedding invitation."
- **Sans: Inter Tight** (400 / 500 / 600 / 700). Used for everything else — UI, body copy, navigation, data, captions. The slightly tightened proportions of Inter Tight pair more comfortably with Garamond than vanilla Inter.

**Rules:**
- Display serif always sets in **medium (500)**, never regular or bold.
- Body sans defaults to **regular (400)** at 16px / 1.55 line-height. Body `text-wrap: pretty` is on.
- Headlines below display size are sans (Inter Tight 600). The serif/sans handoff happens at the H1/Display-S boundary.
- Italics live only in the serif (Cormorant Italic) and only for editorial pull quotes — never UI.
- All-caps copy must have ≥0.08em tracking. Eyebrow caps get 0.16em.

### Spacing

A 4-pixel base. The scale stretches generously toward the top — institutional pages breathe.

`0 · 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128 · 192`

Section padding on marketing surfaces is typically `--sp-9` (96px) vertical at desktop. Cards and forms use `--sp-5` to `--sp-6` (24–32px) inner padding.

### Backgrounds

- **No gradients.** None. Solid fields only.
- **No glassmorphism / blur.** Light blur is used only on a portrait/photo modal scrim, never as a UI material.
- **One full-bleed photograph per marketing page**, used as a hero. Photography is warm-toned, slow, observational — landscapes, hands, light through windows, archival textures. Never stock-photo "people in a meeting."
- **Subtle parchment texture** is permitted on inverse (conifer) sections at very low opacity — like the grain of fine paper. Optional.

### Animation & motion

Restrained. Institutional things don't bounce.

- Default duration: **220ms**, easing `cubic-bezier(0.4, 0, 0.2, 1)` (standard ease).
- Page transitions: opacity fade only, **220ms**. No translate, no scale.
- Hover transitions: **140ms** — fast but not snappy.
- **No spring physics. No bounce. No scale > 1.02 on hover.** Ever.
- Scroll-linked reveals: opacity 0 → 1 + 8px translate-y, once, 400ms, then never animate again.
- Loading: a single hairline progress bar at the top of the page, 1px tall, conifer-700.

### Hover & press states

- **Links** — hover adds a 1px brass underline that draws in from the left over 140ms. Color does not change.
- **Primary button** — hover darkens background by ~6% (`--conifer-800`), press darkens to `--conifer-900`. No scale. No shadow change.
- **Secondary button** — hover fills the background `--parchment-200`; press to `--parchment-300`.
- **Cards** — on hover, the hairline border darkens from `--border-hairline` to `--border-default`. No lift, no shadow growth.
- **Icon buttons** — hover background goes from transparent to `--parchment-200`.

### Borders & rules

The hairline rule is the workhorse of EdenScale.

- **Default rule:** 1px, `rgba(26, 26, 24, 0.10)` (`--border-hairline`). Used between data rows, around cards, separating sections.
- **Strong rule:** 1px, `rgba(26, 26, 24, 0.18)` (`--border-default`). Used at section breaks.
- Section dividers are full-bleed hairlines. They are doing the work that gradients and shadows do elsewhere — **lean on them**.

### Elevation / shadows

Mostly absent. When present, very gentle.

- `--shadow-xs` — a single 1px hairline shadow, used to indicate a sticky header has detached from the top.
- `--shadow-sm` — soft 2px shadow on dropdown menus and the date picker.
- `--shadow-md` — only on toasts and modals.
- `--shadow-lg` — only on a focus-state image card or the CTA card in the hero.

We **do not** use shadows to make buttons or generic cards feel "lifted." Cards are flat, bordered with a hairline.

### Corner radii

- **Default radius is 0.** Cards, sections, panels, photos — square corners.
- **Inputs and buttons:** `2px` (`--radius-xs`). Just enough to feel intentional, not "soft."
- **Tags / status pills:** `999px` (`--radius-pill`). The only place we go round, and only on small chips.
- Profile/portrait images: square. **No round avatars.**

### Cards

A card is:
- 1px hairline border, no shadow.
- Square corners (or 2px on form/input cards).
- Background: `--bg-surface` (white) on parchment pages, or `--bg-raised` for a subtle distinction.
- Inner padding: 24–32px (`--sp-5` to `--sp-6`).
- A 3-tier internal hierarchy: optional eyebrow (small caps, brass) → title (sans 600 or display 500) → body.

### Layout rules

- **Generous whitespace.** Sections are 96–128px tall vertically.
- **Asymmetric grids favored over symmetric.** Marketing pages frequently use a 7+5 / 8+4 column split rather than 6+6.
- **Type lives on a max width of `--container-text` (880px).** Long lines are forbidden.
- **A single full-bleed image per page**, ideally above the fold.

### Transparency & blur

Used only:
- Modal scrim: `rgba(14, 27, 20, 0.55)` (`--bg-overlay`) — conifer-tinted, no blur, or 4px blur max.
- Image overlay for full-bleed hero text: a **bottom-up linear gradient** `transparent → rgba(14, 27, 20, 0.65)`, only when text sits over a photo. (This is the *only* gradient permitted in the system, and only as a protection.)

### Imagery

- **Color vibe:** warm, slightly desaturated. Candle-lit interiors, golden-hour exteriors, archival paper textures.
- **Subjects:** landscapes, architecture, hands, objects of craft. Sparing use of people; when shown, in candid B&W or warm-toned not-staged photos.
- **Never:** stock business imagery, glass conference rooms, overhead handshake shots, stock-photo diversity boardrooms.
- **Grain:** a fine film-grain treatment is acceptable as a texture overlay on hero images.

---

## Iconography

EdenScale uses **Lucide** as its icon system. Icons are line, 1.5px stroke, 24×24 default with a 1.25 stroke ratio — geometric, restrained, modern. Lucide pairs cleanly with Inter Tight without competing with the serif display.

### Loaded from CDN

```html
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
```

Or as React: `lucide-react`.

### Icon usage rules

- **Always 1.5px stroke** (`stroke-width="1.5"`) — Lucide's default 2px is too heavy against our hairline-rule aesthetic.
- **Sizes:** 16px (inline with body text), 20px (UI controls), 24px (default standalone), 32px (feature blocks).
- **Color:** inherit `currentColor`. Default tone: `var(--fg-secondary)`. Brand emphasis: `var(--fg-brand)`. Brass accent only when paired with an eyebrow label.
- **Fill:** none. We are never using filled icons.
- **No emoji.** Anywhere. Not in headlines, not in feature lists, not in error states.
- **No unicode dingbats** as icons. We have a real icon system; use it.

### Custom marks

The only custom-drawn iconography is the **EdenScale balance-scale mark** (`assets/edenscale-mark.svg`), which is reserved for the logo and favicon use. It is not part of the general icon set.

### Substitution note

If EdenScale licenses a custom icon set (e.g. a bespoke commission, or a system like Phosphor / Geist Icons / Untitled Icons), swap `lucide` for that and update this section. The 1.5px / monoline / unfilled rules carry over regardless of provider.

---

## Quickstart for designers / agents

```html
<link rel="stylesheet" href="colors_and_type.css">
<body class="es-page">
  <div class="es-eyebrow">Approach</div>
  <h1 class="es-display-l">Patient capital, deployed deliberately.</h1>
  <p class="es-body-l">EdenScale invests on a generational horizon …</p>
</body>
```

Every preview card in the `preview/` folder is a working demonstration of one slice of this system — open them to see the tokens applied.
