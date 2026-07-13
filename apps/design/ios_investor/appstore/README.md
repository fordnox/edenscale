# App Store screenshots — Investor iOS app

Marketing screenshots for App Store Connect, generated from the design
reference in `../index.html`. Output is `NN-name-1242x2688.png` — the
iPhone 6.5" display size (1242 × 2688 px), accepted for all iPhone slots.

Upload order (first 3 appear on the app installation sheet):

1. `01-portfolio` — Portfolio home, NAV hero
2. `02-capital-calls` — Capital calls list with open call
3. `03-drawdown` — Drawdown notice with wire instructions
4. `04-fund-detail` — Fund detail, position + performance
5. `05-activity` — Activity timeline
6. `06-signin` — Face ID sign-in
7. `07-documents` — Documents & quarterly letters

## Regenerate

```sh
./build.sh
```

Requires Google Chrome. Each shot is a 414 × 896 pt page rendered
headless at 3× device scale. Sources:

- `src/shots/*.html` — one fragment per screenshot (headline + phone UI)
- `src/canvas.css` — the branded canvas (headline, background, device scale)
- `src/device.css` — phone frame + app UI styles, lifted from `../index.html`
- `pages/` — assembled pages (generated; open in a browser to preview)

Screen content is copied from `../index.html`; if the design page changes,
re-copy the affected screen markup into the matching `src/shots/` fragment.
