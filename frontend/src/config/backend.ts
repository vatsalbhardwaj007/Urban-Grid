const defaultHttpUrl = 'http://localhost:8000'
const configuredHttpUrl = import.meta.env.VITE_URBAN_GRID_API_URL ?? defaultHttpUrl

export const backendConfig = {
  httpUrl: configuredHttpUrl.replace(/\/$/, ''),
  wsUrl: (import.meta.env.VITE_URBAN_GRID_WS_URL ?? configuredHttpUrl.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws/traffic').replace(/\/ws\/traffic\/ws\/traffic$/, '/ws/traffic'),
}
