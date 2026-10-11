import { memo } from 'react'
import type { ControlLoopStatus, ControlMode, HealthResponse, TrafficSnapshot } from '../../types/traffic'
import { selectIntersectionVisual } from '../../selectors/trafficVisuals'

interface Props {
  health: HealthResponse | null
  socketStatus: string
  loopStatus: ControlLoopStatus | null
  selectedJunctionId: string
  trafficByIntersection: TrafficSnapshot
  isAutoRunning: boolean
  onSelectJunction: (id: string) => void
  onSetMode: (mode: ControlMode) => void
  onToggleAutoRun: () => void
  onStep: () => void
  onReset: () => void
  onInjectCongestion: (target?: string) => void
  onResolveCongestion: (target?: string) => void
  onAdjustTimer: (target: string, duration: number) => void
}

export const LeftSidebar = memo(function LeftSidebar({
  health,
  socketStatus,
  loopStatus,
  selectedJunctionId,
  trafficByIntersection,
  isAutoRunning,
  onSelectJunction,
  onSetMode,
  onToggleAutoRun,
  onStep,
  onReset,
  onInjectCongestion,
  onResolveCongestion,
  onAdjustTimer,
}: Props) {
  const currentMode = loopStatus?.mode ?? 'AUTO'
  const isSumoConnected = health?.simulation_connected === true
  const isWsConnected = socketStatus === 'connected'

  const junctions = ['I1', 'I2', 'I3', 'I4']

  const getJunctionColor = (id: string) => {
    const traffic = trafficByIntersection[id]
    if (!traffic) return '#64748b'
    const vis = selectIntersectionVisual(traffic)
    if (vis.status === 'critical') return '#ef4444'
    if (vis.status === 'moderate') return '#f59e0b'
    return '#00f0a0'
  }

  const selectedTraffic = trafficByIntersection[selectedJunctionId]
  const selectedVis = selectIntersectionVisual(selectedTraffic)

  return (
    <aside className="ug-left-sidebar" aria-label="Control & System Surface">
      {/* 1. SYSTEM STATUS */}
      <section className="ug-section">
        <div className="section-title">SYSTEM STATUS</div>
        <div className="system-status-grid">
          <div className="status-row">
            <span className="status-name">FastAPI Backend</span>
            <span className={`status-badge ${health ? 'healthy' : 'down'}`}>
              <i className="status-dot" /> {health ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-name">SUMO Simulator</span>
            <span className={`status-badge ${isSumoConnected ? 'healthy' : 'down'}`}>
              <i className="status-dot" /> {isSumoConnected ? 'RUNNING' : 'STOPPED'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-name">AI Engine</span>
            <span className={`status-badge ${loopStatus ? 'healthy' : 'idle'}`}>
              <i className="status-dot" /> {loopStatus ? 'ACTIVE' : 'READY'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-name">Telemetry Stream</span>
            <span className={`status-badge ${isWsConnected ? 'healthy' : 'down'}`}>
              <i className="status-dot" /> {isWsConnected ? 'LIVE' : 'POLLING'}
            </span>
          </div>
        </div>
      </section>

      {/* 2. CONGESTION SCENARIO & AI PREVENTION CONTROLLER */}
      <section className="ug-section ug-congestion-ctrl">
        <div className="section-title">
          <span>⚡ CONGESTION & AI CONTROLS</span>
        </div>
        <div className="scenario-btn-stack">
          <button
            className="scenario-btn surge"
            onClick={() => onInjectCongestion('I2')}
            title="Simulate sudden traffic demand spike at I2 to cause congestion buildup"
          >
            🔴 Build Congestion (I2 Spike)
          </button>
          <button
            className="scenario-btn resolve"
            onClick={() => onResolveCongestion('I2')}
            title="Actuate adaptive signal timing to flush queued vehicles and prevent gridlock"
          >
            ⚡ Prevent Congestion (AI Optimize)
          </button>
        </div>
      </section>

      {/* 3. TRAFFIC SIGNAL TIMER ADJUSTER */}
      <section className="ug-section ug-signal-adjuster">
        <div className="section-title">
          <span>⏱ SIGNAL TIMER: {selectedJunctionId}</span>
        </div>
        <div className="timer-readout-card">
          <div className="timer-current-row">
            <span className="timer-phase-tag">
              {selectedVis.phase === 'GREEN' ? '🟢 GREEN' : selectedVis.phase === 'RED' ? '🔴 RED' : '🟡 YELLOW'}
            </span>
            <span className="timer-seconds-big">
              {selectedVis.greenRemaining !== null ? `${selectedVis.greenRemaining.toFixed(0)}s` : '--'}
            </span>
          </div>
          <div className="timer-quick-actions">
            <button
              className="quick-time-btn"
              onClick={() => onAdjustTimer(selectedJunctionId, (selectedVis.greenRemaining || 30) + 10)}
            >
              +10s
            </button>
            <button
              className="quick-time-btn"
              onClick={() => onAdjustTimer(selectedJunctionId, (selectedVis.greenRemaining || 30) + 20)}
            >
              +20s
            </button>
            <button
              className="quick-time-btn max"
              onClick={() => onAdjustTimer(selectedJunctionId, 45)}
            >
              Set 45s
            </button>
          </div>
        </div>
      </section>

      {/* 4. CONTROL MODE */}
      <section className="ug-section">
        <div className="section-title">CONTROL MODE</div>
        <div className="control-mode-buttons">
          <button
            className={`mode-btn auto ${currentMode === 'AUTO' ? 'active' : ''}`}
            onClick={() => onSetMode('AUTO')}
            title="Automated closed-loop AI control"
          >
            <span className="mode-tag">AI</span>
            <span className="mode-name">AUTO</span>
          </button>
          <button
            className={`mode-btn manual ${currentMode === 'MANUAL' ? 'active' : ''}`}
            onClick={() => onSetMode('MANUAL')}
            title="Manual operator override"
          >
            <span className="mode-tag">OP</span>
            <span className="mode-name">MANUAL</span>
          </button>
          <button
            className={`mode-btn emergency ${currentMode === 'EMERGENCY' ? 'active' : ''}`}
            onClick={() => onSetMode('EMERGENCY')}
            title="Emergency corridor priority override"
          >
            <span className="mode-tag">PRIO</span>
            <span className="mode-name">EMERGENCY</span>
          </button>
        </div>
      </section>

      {/* 5. INTERSECTIONS */}
      <section className="ug-section">
        <div className="section-title">MONITORED NODES</div>
        <div className="intersection-chips-grid">
          {junctions.map((id) => (
            <button
              key={id}
              className={`node-chip ${selectedJunctionId === id ? 'selected' : ''}`}
              onClick={() => onSelectJunction(id)}
            >
              <i className="node-dot" style={{ backgroundColor: getJunctionColor(id) }} />
              <span className="node-id">{id}</span>
              <span className="node-queue">
                {trafficByIntersection[id] ? `${trafficByIntersection[id].total_queue}q` : '--'}
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* 6. SIMULATION CONTROLS */}
      <section className="ug-section ug-sim-controls">
        <div className="section-title">SIMULATION CONTROLS</div>
        <div className="sim-buttons-row">
          <button
            className={`sim-btn run-btn ${isAutoRunning ? 'running' : ''}`}
            onClick={onToggleAutoRun}
          >
            {isAutoRunning ? '❚❚ Pause' : '▶ Run Loop'}
          </button>
          <button className="sim-btn step-btn" onClick={onStep} disabled={isAutoRunning}>
            ⏭ Step
          </button>
        </div>
        <button className="sim-btn-secondary reset-btn" onClick={onReset}>
          ↺ Reset View
        </button>
        <div className="cycle-readout">
          Cycle #{loopStatus?.current_cycle ?? 0} · {loopStatus?.decision_engine ?? 'M1 Engine'}
        </div>
      </section>
    </aside>
  )
})
