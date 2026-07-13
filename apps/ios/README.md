# NewTaven Investor — iOS app

A native iOS app for limited partners, built by wrapping the existing investor
SPA (`apps/investor`) in [Capacitor](https://capacitorjs.com). The web bundle is
compiled and copied into a real Xcode project you sign with your own Apple
Developer certificates and submit to the App Store — no separate codebase to
maintain, and every screen stays in sync with the web portal.

Design reference for the app's look and feel: [`apps/design/ios_investor`](../design/ios_investor/index.html).

---

## TL;DR

```bash
cp apps/ios/.env.example apps/ios/.env   # then edit: API URL, Hanko URL, Team ID
make ios                                 # build web → sync → open Xcode
# In Xcode: Signing & Capabilities ▸ pick your Team ▸ Product ▸ Archive ▸ Distribute
```

Prefer a headless signed build:

```bash
make ios-archive                         # → apps/ios/build/ipa/App.ipa
```

---

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| **Full Xcode** (not just Command Line Tools) | build, sign, archive | Mac App Store, then `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer` |
| **CocoaPods** | Capacitor native deps | `sudo gem install cocoapods` |
| **Node + pnpm** | build the web bundle | already used by this repo |
| **Apple Developer Program** membership | signing & submission | [developer.apple.com](https://developer.apple.com) ($99/yr) |

`make ios-check` verifies Xcode and CocoaPods and tells you what's missing.

> This repo's dev container ships only the Command Line Tools, so `make ios`
> must be run on a Mac with the full Xcode installed.

---

## Configuration

All build-time config lives in `apps/ios/.env` (git-ignored). Copy the example
and fill it in:

```bash
cp apps/ios/.env.example apps/ios/.env
```

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Public **https** API base URL. Never `localhost` for a device build. |
| `VITE_HANKO_API_URL` | Your Hanko project URL (auth). |
| `VITE_APP_TITLE`, `VITE_APP_URL` | App title / marketing URL used by the SPA. |
| `IOS_BUNDLE_ID` | Reverse-DNS bundle id, e.g. `com.newtaven.investor`. Register it in the Developer portal. |
| `IOS_APP_NAME` | Display name under the icon. |
| `APPLE_TEAM_ID` | Your Team ID (Developer portal ▸ Membership). Needed for `make ios-archive`. |
| `CAP_SERVER_URL` | Optional — load a live origin instead of bundled assets (see Authentication). |

---

## How it works

```
apps/investor  ──vite build --base=/──▶  dist/  ──copy──▶  apps/ios/www/
                                                                │
                                                     cap sync ios
                                                                ▼
                                          apps/ios/ios/App/App.xcworkspace  (Xcode)
```

1. `scripts/prepare.sh` loads `.env`, builds the investor SPA with `--base=/`
   (so assets resolve at the Capacitor web root instead of `/investor/`), and
   copies `dist/` into `www/`.
2. On first run it generates the native project with `cap add ios`, then
   `cap sync ios` copies the web assets and installs native pods.
3. `make ios` opens the workspace in Xcode; `make ios-archive` builds and
   exports a signed IPA non-interactively.

Native niceties included via official plugins: splash screen (conifer),
status-bar styling (dark glyphs on parchment), keyboard handling, and app
lifecycle/back-button. Configure them in `capacitor.config.ts`.

---

## Signing & submitting to the App Store

You sign with **your** keys — nothing here contains or asks for your
credentials. Two paths:

### A. Through Xcode (recommended first time)

1. `make ios`
2. In Xcode, select the **App** target ▸ **Signing & Capabilities**.
3. Check **Automatically manage signing** and choose your **Team**. Xcode
   creates/downloads the distribution certificate and provisioning profile.
4. **Product ▸ Archive**, then **Distribute App ▸ App Store Connect**.

### B. Headless — `make ios-archive`

1. Set `APPLE_TEAM_ID` (and ideally a matching `IOS_BUNDLE_ID`) in `.env`.
2. `make ios-archive` → `apps/ios/build/ipa/App.ipa` (signed, App Store method).
3. Upload it:
   - **Transporter.app** — drag in the `.ipa`, Deliver; or
   - `xcrun altool --upload-app -f apps/ios/build/ipa/App.ipa -t ios -u <apple-id> -p <app-specific-password>`
     (create an app-specific password at appleid.apple.com).

Before your first upload, create the app record in
[App Store Connect](https://appstoreconnect.apple.com) with the same
`IOS_BUNDLE_ID`.

---

## Authentication (read this before shipping)

The investor app authenticates with Hanko and reads its session from the
`hanko` **cookie** (`packages/auth/src/hanko.ts`), and login uses **passkeys /
WebAuthn**. Two consequences inside a `WKWebView`:

- **Bundled mode** (default, `capacitor://localhost`) does **not** share cookies
  with your API/Hanko origin, so cookie-based sessions won't be visible and
  login will likely fail.
- **WebAuthn** needs the [Associated Domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains)
  entitlement (`webcredentials:<your-domain>`) and a matching
  `apple-app-site-association` file served from that domain.

**Simplest path that works today:** run in **hosted mode** — set
`CAP_SERVER_URL=https://newtaven.com/investor` in `.env`. The webview then loads
your real https origin, so cookies and passkeys behave exactly as in Safari. The
native shell still provides the icon, splash, status bar, and App Store
presence.

**Fully offline/bundled** auth is possible but needs app work: add the
Associated Domains entitlement and switch session storage from a cookie to a
token in `localStorage`/Capacitor Preferences. Track that separately before
going bundled.

> Also add `capacitor://localhost` (and your hosted origin) to the backend's
> `CORS_ALLOW_ORIGINS`.

---

## Native project: generated vs. committed

The `ios/` folder is **generated** by `cap add ios` and is git-ignored by
default, because it needs Xcode + CocoaPods and can't be produced in CI-only
environments. That's fine while it's disposable.

Once you customize native config — **app icons, launch screen, entitlements
(Associated Domains, Push), `Info.plist`, version/build numbers** — you'll want
it tracked. Remove the `ios/` line from `.gitignore` and commit the folder.
`cap sync` is safe to re-run over a committed project; it won't clobber your
native changes.

App icons & splash: drop a 1024×1024 icon and run
`pnpm dlx @capacitor/assets generate --ios`.

---

## Common tasks

| Command | Does |
|---|---|
| `make ios` | Build web, sync, open Xcode |
| `make ios-archive` | Build a signed App Store IPA |
| `make ios-check` | Verify Xcode + CocoaPods are installed |
| `cd apps/ios && pnpm exec cap sync ios` | Re-copy web assets after a code change |
| `cd apps/ios && pnpm exec cap run ios` | Build & launch on a simulator/device |

---

## Troubleshooting

- **Blank screen on launch** — assets didn't resolve. Confirm the build ran with
  `--base=/` (it does via `prepare.sh`) and that `www/index.html` exists.
- **Network/API errors** — `VITE_API_URL` points at `localhost`, or the backend
  CORS list is missing the app origin.
- **Can't log in** — the cookie/WebAuthn issue above; try `CAP_SERVER_URL`
  (hosted mode).
- **`xcodebuild` "requires Xcode"** — you have only Command Line Tools; install
  full Xcode and run the `xcode-select -s …` command from Prerequisites.
- **Signing failures in `make ios-archive`** — verify `APPLE_TEAM_ID`, that
  you're signed into the account in Xcode ▸ Settings ▸ Accounts, and that the
  bundle id exists in the Developer portal. `-allowProvisioningUpdates` lets
  Xcode create the profile automatically.
