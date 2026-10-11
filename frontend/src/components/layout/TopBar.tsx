import type { ConnectionStatus } from '../../state/trafficStore'
import type { DashboardScreen } from '../../data/dashboardNavigation'
import type { HealthResponse } from '../../types/traffic'
import { Icon } from '../Icon'

const labels: Record<ConnectionStatus, string> = { connecting: 'Connecting', connected: 'Live connection', reconnecting: 'Reconnecting', 'rest-fallback': 'REST fallback', 'telemetry-stale': 'Telemetry stale', 'backend-unavailable': 'Backend unavailable', 'sumo-unavailable': 'SUMO unavailable' }

export function TopBar({ status, health, lastReceivedAt, screen, onNavigate }: { status: ConnectionStatus; health: HealthResponse | null; lastReceivedAt: number | null; screen: DashboardScreen; onNavigate: (screen: DashboardScreen) => void }) {
  const simulationLabel = health?.simulation_connected ? status === 'connected' ? 'SUMO ONLINE' : 'SUMO LAST ONLINE' : health ? 'SUMO UNAVAILABLE' : 'SUMO UNKNOWN'
  return <header className="topbar">
    <div className="brand"><div className="brand-mark"><i/><i/><i/><i/></div><div><div className="brand-title">URBAN <b>GRID</b></div><div className="brand-sub">INTELLIGENCE SYSTEMS</div></div></div>
    <nav className="nav" aria-label="Primary"><button className={screen === 'live' ? 'active' : ''} aria-current={screen === 'live' ? 'page' : undefined} onClick={() => onNavigate('live')}><Icon name="activity" size={16} />Live View</button><button className={screen === 'analytics' ? 'active' : ''} aria-current={screen === 'analytics' ? 'page' : undefined} onClick={() => onNavigate('analytics')}>Analytics</button><button disabled title="Route telemetry is not available yet">Routes</button><button disabled title="Alerts are not available yet">Alerts</button></nav>
    <div className="mobile-screen-switcher" role="group" aria-label="Primary"><button className={screen === 'live' ? 'active' : ''} aria-pressed={screen === 'live'} onClick={() => onNavigate('live')}>Live</button><button className={screen === 'analytics' ? 'active' : ''} aria-pressed={screen === 'analytics'} onClick={() => onNavigate('analytics')}>Analytics</button></div>
    <div className="top-status"><span className={`connection-pill connection-${status}`}><i/>{labels[status]}</span><span className="simulation-status">{simulationLabel}</span><span className="last-update" title="Last traffic state received">{lastReceivedAt ? new Date(lastReceivedAt).toLocaleTimeString() : '—'}</span><span className="avatar">UG</span></div>
  </header>
}
