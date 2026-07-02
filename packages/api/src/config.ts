export interface Config {
  VITE_APP_TITLE: string;
  VITE_APP_EMAIL: string;
  VITE_APP_URL: string;
  VITE_HANKO_API_URL: string;
  VITE_DEV_STORAGE_TOKEN: string;
}

export const config: Config = {
  VITE_APP_TITLE: import.meta.env.VITE_APP_TITLE || "NewTaven",
  VITE_APP_EMAIL: import.meta.env.VITE_APP_EMAIL || "fordnox@gmail.com",
  VITE_APP_URL: import.meta.env.VITE_APP_URL || "https://example.com",
  VITE_HANKO_API_URL: import.meta.env.VITE_HANKO_API_URL || "",
  VITE_DEV_STORAGE_TOKEN: import.meta.env.VITE_DEV_STORAGE_TOKEN || "dev-storage",
};
