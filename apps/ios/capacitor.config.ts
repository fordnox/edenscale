import type { CapacitorConfig } from '@capacitor/cli'

// Build-time identifiers come from apps/ios/.env (loaded by scripts/prepare.sh).
// The defaults are safe placeholders — set IOS_BUNDLE_ID to your own reverse-DNS
// identifier before you ship, and register it in the Apple Developer portal.
const bundleId = process.env.IOS_BUNDLE_ID || 'com.newtaven.investor'
const appName = process.env.IOS_APP_NAME || 'NewTaven Investor'

// Hosted mode: when CAP_SERVER_URL is set the WKWebView loads that live https
// origin instead of the bundled assets in ./www. This is usually required for
// Hanko passkey + cookie auth to work — see README ▸ Authentication.
const serverUrl = process.env.CAP_SERVER_URL || undefined

const config: CapacitorConfig = {
  appId: bundleId,
  appName,
  webDir: 'www',
  ios: {
    // Let the web content lay itself out under the notch / home indicator; the
    // investor app already handles safe-area padding via its layout.
    contentInset: 'always',
    backgroundColor: '#FBF9F4', // parchment-50, matches the app page background
  },
  server: {
    iosScheme: 'capacitor',
    ...(serverUrl ? { url: serverUrl } : {}),
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 500,
      launchAutoHide: true,
      backgroundColor: '#16291F', // conifer-800
      showSpinner: false,
    },
    StatusBar: {
      style: 'DARK', // dark glyphs over the light parchment app chrome
      backgroundColor: '#FBF9F4',
    },
  },
}

export default config
