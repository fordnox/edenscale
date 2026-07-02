interface ImportMetaEnv {
  readonly VITE_APP_TITLE?: string
  readonly VITE_APP_SLOGAN?: string
  readonly VITE_APP_EMAIL?: string
  readonly VITE_APP_URL?: string
  readonly VITE_API_URL?: string
  readonly VITE_GITHUB_URL?: string
  readonly VITE_HANKO_API_URL?: string
  readonly VITE_DEV_STORAGE_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
