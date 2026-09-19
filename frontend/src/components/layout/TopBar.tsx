import type { ConnectionStatus } from '../../state/trafficStore'
import type { HealthResponse } from '../../types/traffic'
import { Icon } from '../Icon'

const labels: Record<ConnectionStatus, string> = { connecting: 'Connecting', connected: 'Live connection', disconnected: 'Disconnected', reconnecting: 'Reconnecting' }

export function TopBar({ status, health, lastReceivedAt }: { status: ConnectionStatus; health: HealthResponse | null; lastReceivedAt: number | null }) {
  const simulationLabel = health?.simulation_connected ? status === 'connected' ? 'SUMO ONLINE' : 'SUMO LAST ONLINE' : health ? 'SUMO OFFLINE' : 'SUMO UNKNOWN'
  return <header className="topbar">
    <div className="brand"><div className="brand-mark"><i/><i/><i/><i/></div><div><div className="brand-title">URBAN <b>GRID</b></div><div className="brand-sub">INTELLIGENCE SYSTEMS</div></div></div>
    <nav className="nav" aria-label="Primary"><span className="active"><Icon name="activity" size={16} />Live View</span><button disabled title="Analytics is not connected yet">Analytics</button><button disabled title="Route telemetry is not available yet">Routes</button><button disabled title="Alerts are not available yet">Alerts</button></nav>
    <div className="top-status"><span className={`connection-pill connection-${status}`}><i/>{labels[status]}</span><span className="simulation-status">{simulationLabel}</span><span className="last-update" title="Last traffic state received">{lastReceivedAt ? new Date(lastReceivedAt).toLocaleTimeString() : '—'}</span><span className="avatar">UG</span></div>
  </header>
}
