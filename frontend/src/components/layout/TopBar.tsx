import { memo } from 'react'
import type { ConnectionStatus } from '../../state/trafficStore'
import type { HealthResponse } from '../../types/traffic'

interface Props {
  status: ConnectionStatus
  health: HealthResponse | null
  lastSimulationTimestamp: number | null
  activeNav: string
  onNavChange: (nav: string) => void
}

export const TopBar = memo(function TopBar({
  status,
  health,
  lastSimulationTimestamp,
  activeNav,
  onNavChange,
}: Props) {
  const isConnected = status === 'connected' && health?.simulation_connected === true

  return (
    <header className="ug-topbar">
      {/* Brand & Tagline */}
      <div className="ug-brand">
        <div className="ug-logo-icon">
          <span className="dot dot-1" />
          <span className="dot dot-2" />
          <span className="dot dot-3" />
          <span className="dot dot-4" />
        </div>
        <div className="ug-brand-text">
          <div className="ug-title">
            URBAN <span className="ug-highlight">GRID</span>
          </div>
          <div className="ug-tagline">Smarter Intersections. Smoother Cities.</div>
        </div>
      </div>

      {/* Core Loop Indicator */}
      <div className="ug-core-loop" title="Closed-Loop Autonomous Architecture">
        <span className="loop-step">SENSE</span>
        <span className="loop-arrow">→</span>
        <span className="loop-step highlight">PREDICT</span>
        <span className="loop-arrow">→</span>
        <span className="loop-step highlight">OPTIMIZE</span>
        <span className="loop-arrow">→</span>
        <span className="loop-step">ACT</span>
        <span className="loop-arrow">→</span>
        <span className="loop-step">MEASURE</span>
      </div>

      {/* Primary Navigation Tabs */}
      <nav className="ug-nav" aria-label="Primary Navigation">
        {['Live View', 'Analytics', 'Control', 'Simulation'].map((tab) => (
          <button
            key={tab}
            className={`ug-nav-btn ${activeNav === tab ? 'active' : ''}`}
            onClick={() => onNavChange(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      {/* Live System Status & Simulation Clock */}
      <div className="ug-top-status">
        <div className={`ug-pill ${isConnected ? 'status-online' : 'status-offline'}`}>
          <span className="pulse-indicator" />
          {status.toUpperCase()}
        </div>
        <div className="ug-pill time-pill">
          <span className="pill-label">SIM TIME:</span>
          <span className="pill-val">
            {lastSimulationTimestamp !== null ? `T+${lastSimulationTimestamp.toFixed(1)}s` : 'T+0.0s'}
          </span>
        </div>
      </div>
    </header>
  )
})
