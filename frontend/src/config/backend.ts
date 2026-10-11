const defaultHttpUrl = 'http://localhost:8000'
const withoutTrailingSlash = (url: string) => url.replace(/\/+$/, '')
const configuredHttpUrl = withoutTrailingSlash(import.meta.env.VITE_URBAN_GRID_API_URL ?? defaultHttpUrl)
const configuredWsUrl = withoutTrailingSlash(import.meta.env.VITE_URBAN_GRID_WS_URL ?? configuredHttpUrl.replace(/^http/, 'ws'))

export const backendConfig = {
  httpUrl: configuredHttpUrl,
  wsUrl: configuredWsUrl.endsWith('/ws/traffic') ? configuredWsUrl : `${configuredWsUrl}/ws/traffic`,
}
