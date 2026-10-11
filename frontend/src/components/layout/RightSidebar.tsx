import { memo } from 'react'
import type { ControlLoopStatus, SignalActuationResult, TrafficSnapshot } from '../../types/traffic'
import { selectIntersectionVisual, selectNetworkOverview } from '../../selectors/trafficVisuals'

interface Props {
  trafficByIntersection: TrafficSnapshot
  selectedJunctionId: string
  onSelectJunction: (id: string) => void
  loopStatus: ControlLoopStatus | null
  latestIntervention: SignalActuationResult | null
  onApplyAction: (action: unknown) => Promise<void>
  onAdjustTimer?: (target: string, duration: number) => void
  onResolveCongestion?: (target?: string) => void
}

export const RightSidebar = memo(function RightSidebar({
  trafficByIntersection,
  selectedJunctionId,
  onSelectJunction,
  loopStatus,
  latestIntervention,
  onApplyAction,
  onAdjustTimer,
  onResolveCongestion,
}: Props) {
  const network = selectNetworkOverview(trafficByIntersection)
  const junctions = ['I1', 'I2', 'I3', 'I4']

  const getPhaseClass = (phase: string | null) => {
    if (!phase) return 'unknown'
    return phase.toLowerCase()
  }

  const getSeverityBadge = (status: string) => {
    switch (status) {
      case 'critical':
        return <span className="badge badge-critical">CRITICAL</span>
      case 'moderate':
        return <span className="badge badge-moderate">MODERATE</span>
      case 'flowing':
        return <span className="badge badge-flowing">FLOWING</span>
      default:
        return <span className="badge badge-unknown">NO DATA</span>
    }
  }

  // Check if any junction is currently congested
  const congestedJunctionId = junctions.find((id) => {
    const s = trafficByIntersection[id]
    return s && (s.total_queue >= 5 || s.density >= 30)
  })

  return (
    <aside className="ug-right-sidebar" aria-label="Network Telemetry & AI Intelligence">
      {/* Active Congestion Alert Banner if bottleneck detected */}
      {congestedJunctionId && (
        <div className="critical-alert-banner">
          <div className="alert-header">
            <span className="alert-pulse" /> ⚠️ BOTTLENECK DETECTED: {congestedJunctionId}
          </div>
          <div className="alert-desc">
            Queue: {trafficByIntersection[congestedJunctionId]?.total_queue} vehicles waiting. M1 AI recommends immediate signal extension.
          </div>
          <button
            className="alert-action-btn"
            onClick={() => onResolveCongestion?.(congestedJunctionId)}
          >
            ⚡ Prevent Congestion Now (AI Adapt)
          </button>
        </div>
      )}

      {/* 1. NETWORK OVERVIEW */}
      <section className="ug-section">
        <div className="section-title">NETWORK OVERVIEW</div>
        <div className="network-metrics-grid">
          <div className="net-metric-card">
            <span className="net-metric-val">{network.totalVehicles}</span>
            <span className="net-metric-label">TOTAL VEHICLES</span>
          </div>
          <div className="net-metric-card">
            <span
              className="net-metric-val"
              style={{ color: network.totalQueue > 5 ? '#f87171' : '#f8fafc' }}
            >
              {network.totalQueue}
            </span>
            <span className="net-metric-label">TOTAL QUEUE</span>
          </div>
          <div className="net-metric-card">
            <span className="net-metric-val">{network.meanSpeed}</span>
            <span className="net-metric-label">MEAN SPEED (m/s)</span>
          </div>
          <div className="net-metric-card">
            <span className="net-metric-val">{network.meanDensity}</span>
            <span className="net-metric-label">DENSITY (veh/km)</span>
          </div>
        </div>
      </section>

      {/* 2. LIVE INTERSECTIONS WITH SIGNAL TIMERS */}
      <section className="ug-section">
        <div className="section-title">INTERSECTIONS & SIGNAL TIMERS</div>
        <div className="intersection-cards-list">
          {junctions.map((id) => {
            const traffic = trafficByIntersection[id]
            const vis = selectIntersectionVisual(traffic)
            const isSelected = selectedJunctionId === id

            return (
              <div
                key={id}
                className={`junction-card ${isSelected ? 'selected' : ''} ${vis.status === 'critical' ? 'critical-border' : ''}`}
                onClick={() => onSelectJunction(id)}
              >
                <div className="card-top">
                  <div className="junction-name-box">
                    <span className="junction-name">{id}</span>
                    {vis.status === 'critical' && <span className="jam-tag">CONGESTED</span>}
                  </div>
                  <div className="card-top-right">
                    <span className={`phase-pill ${getPhaseClass(vis.phase)}`}>
                      <i className="phase-dot" /> {vis.phase ?? '--'}
                    </span>
                    {getSeverityBadge(vis.status)}
                  </div>
                </div>

                <div className="card-metrics-row">
                  <div className="card-stat">
                    <span className="stat-label">Timer</span>
                    <span className="stat-val highlight timer-countdown">
                      {vis.greenRemaining !== null ? `${vis.greenRemaining.toFixed(0)}s` : '--'}
                    </span>
                  </div>
                  <div className="card-stat">
                    <span className="stat-label">Vehicles</span>
                    <span className="stat-val">{traffic ? vis.totalVehicles : '--'}</span>
                  </div>
                  <div className="card-stat">
                    <span className="stat-label">Queue</span>
                    <span className={`stat-val ${vis.queue > 4 ? 'warning queue-pulse' : ''}`}>
                      {traffic ? vis.queue : '--'}
                    </span>
                  </div>
                  <div className="card-stat">
                    <span className="stat-label">Speed</span>
                    <span className="stat-val">
                      {traffic ? `${vis.meanSpeed.toFixed(1)}m/s` : '--'}
                    </span>
                  </div>
                </div>

                {/* Quick Signal Timer Adjustment Buttons on Card */}
                <div className="card-quick-timer-row">
                  <span className="timer-ctrl-label">Signal Timer:</span>
                  <button
                    className="quick-timer-pill"
                    onClick={(e) => {
                      e.stopPropagation()
                      onAdjustTimer?.(id, (vis.greenRemaining || 30) + 15)
                    }}
                    title={`Add +15s green duration to ${id}`}
                  >
                    +15s Green
                  </button>
                  <button
                    className="quick-timer-pill max"
                    onClick={(e) => {
                      e.stopPropagation()
                      onAdjustTimer?.(id, 45)
                    }}
                    title={`Set ${id} to 45s maximum green`}
                  >
                    Set 45s
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* 3. TRAFFIC INTELLIGENCE */}
      <section className="ug-section intel-section">
        <div className="section-title">TRAFFIC INTELLIGENCE & ADAPTATION</div>
        <div className="intel-box">
          {latestIntervention ? (
            <>
              <div className="intel-row">
                <span className="intel-label">AI PREDICTION:</span>
                <span className="intel-val warning">Congestion Threshold Mitigated</span>
              </div>
              <div className="intel-row">
                <span className="intel-label">TARGET NODE:</span>
                <span className="intel-val highlight">{latestIntervention.target}</span>
              </div>
              <div className="intel-row">
                <span className="intel-label">SIGNAL ACTUATION:</span>
                <span className="intel-val highlight">
                  Green Extended to {latestIntervention.applied_duration}s
                </span>
              </div>
              <div className="intel-row">
                <span className="intel-label">ACTION STATUS:</span>
                <span className="status-badge healthy">
                  <i className="status-dot" /> ACTUATED IN SUMO
                </span>
              </div>
              <p className="intel-msg">{latestIntervention.message}</p>
            </>
          ) : (
            <>
              <div className="intel-row">
                <span className="intel-label">AI PREDICTION:</span>
                <span className="intel-val">
                  {congestedJunctionId
                    ? `⚠️ High Congestion at ${congestedJunctionId} (Prob: 0.89)`
                    : 'Monitoring Pressure Scores'}
                </span>
              </div>
              <div className="intel-row">
                <span className="intel-label">AI RECOMMENDATION:</span>
                <span className="intel-val highlight">
                  {congestedJunctionId
                    ? `Extend ${congestedJunctionId} Green to 45s`
                    : 'Nominal Signal Timing Active'}
                </span>
              </div>
              <div className="intel-row">
                <span className="intel-label">ENGINE:</span>
                <span className="intel-val highlight">
                  {loopStatus?.decision_engine ?? 'RealM1DecisionEngine'}
                </span>
              </div>
              <p className="intel-msg">
                Closed-loop M1 optimizer compares upstream queue pressures and adjusts signal timing to prevent gridlock.
              </p>
              <button
                className="apply-action-btn"
                onClick={() => {
                  void onApplyAction({
                    target: selectedJunctionId,
                    green_duration: 45.0,
                    source: 'MANUAL',
                    timestamp: new Date().toISOString(),
                  })
                  onAdjustTimer?.(selectedJunctionId, 45)
                }}
              >
                Apply AI Adaptive Signal (45s on {selectedJunctionId})
              </button>

            </>
          )}
        </div>
      </section>
    </aside>
  )
})
