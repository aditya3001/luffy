/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_WEBSOCKET_URL: string
  readonly VITE_ENABLE_MOCK: string
  readonly VITE_LOG_LEVEL: string
  // Add more environment variables as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
