import type { ConnectionStatus } from '../../state/trafficStore'
import type { HealthResponse } from '../../types/traffic'

const labels: Record<ConnectionStatus, string> = { booting: 'CONNECTING', live: 'LIVE', polling: 'REST FALLBACK', reconnecting: 'RECONNECTING', stale: 'STALE DATA', unavailable: 'BACKEND UNAVAILABLE' }

export function TopBar({ status, health, lastReceivedAt }: { status: ConnectionStatus; health: HealthResponse | null; lastReceivedAt: number | null }) {
  return <header className="topbar"><div className="brand"><div className="brand-mark"><i/><i/><i/><i/></div><div><div className="brand-title">URBAN <b>GRID</b></div><div className="brand-sub">INTELLIGENCE SYSTEMS</div></div></div><nav className="nav" aria-label="Primary"><button className="active">⌁ &nbsp;Live View</button><button>◌ &nbsp;Analytics</button><button>⌘ &nbsp;Routes</button><button>♧ &nbsp;Alerts</button></nav><div className="top-status"><span className="status-pill"><i/> {labels[status]}</span><span className="status-pill"><i/> {health?.simulation_connected ? 'SUMO CONNECTED' : 'SUMO STATUS UNKNOWN'}</span><b>{lastReceivedAt ? new Date(lastReceivedAt).toLocaleTimeString() : '—'}</b><span>⌕</span><span className="avatar">AG</span></div></header>
}
