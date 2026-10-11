export type DashboardScreen = 'live' | 'analytics'

export function dashboardScreenFromHash(hash: string): DashboardScreen { return hash === '#analytics' ? 'analytics' : 'live' }
export function dashboardHash(screen: DashboardScreen) { return screen === 'analytics' ? '#analytics' : '' }
