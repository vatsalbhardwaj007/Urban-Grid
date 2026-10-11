// oxlint-disable react/preserve-manual-memoization
import { memo, useMemo } from 'react'
import type { TrafficSnapshot } from '../../types/traffic'
import { selectIntersectionVisual } from '../../selectors/trafficVisuals'

type Props = {
  trafficByIntersection: TrafficSnapshot
  selectedJunctionId: string
  onSelectJunction: (id: string) => void
  latestIntervention: { target: string; applied_duration: number; current_phase: string; source: string; message: string } | null
  onAdjustTimer?: (target: string, duration: number) => void
  onInjectCongestion?: (target?: string) => void
  onResolveCongestion?: (target?: string) => void
}

interface NodeCoord {
  id: string
  name: string
  x: number
  y: number
}

const NODES: Record<string, NodeCoord> = {
  I1: { id: 'I1', name: 'NW Junction (I1)', x: 230, y: 150 },
  I2: { id: 'I2', name: 'NE Junction (I2)', x: 670, y: 150 },
  I3: { id: 'I3', name: 'SW Junction (I3)', x: 230, y: 410 },
  I4: { id: 'I4', name: 'SE Junction (I4)', x: 670, y: 410 },
}

export const TrafficMap = memo(function TrafficMap({
  trafficByIntersection,
  selectedJunctionId,
  onSelectJunction,
  latestIntervention,
  onAdjustTimer,
  onInjectCongestion,
  onResolveCongestion,
}: Props) {
  // Visual states for all 4 intersections
  const vI1 = selectIntersectionVisual(trafficByIntersection.I1)
  const vI2 = selectIntersectionVisual(trafficByIntersection.I2)
  const vI3 = selectIntersectionVisual(trafficByIntersection.I3)
  const vI4 = selectIntersectionVisual(trafficByIntersection.I4)

  const visuals: Record<string, typeof vI1> = { I1: vI1, I2: vI2, I3: vI3, I4: vI4 }

  const statusColor = (status: string) => {
    switch (status) {
      case 'critical':
        return '#ef4444'
      case 'moderate':
        return '#f59e0b'
      case 'flowing':
        return '#00f0a0'
      default:
        return '#38bdf8'
    }
  }

  // Corridors status based on endpoints
  const corridorStatus = (idA: string, idB: string) => {
    const sA = visuals[idA]?.congestion ?? 0
    const sB = visuals[idB]?.congestion ?? 0
    const maxScore = Math.max(sA, sB)
    if (maxScore >= 65) return '#ef4444'
    if (maxScore >= 35) return '#f59e0b'
    return '#00f0a0'
  }

  // Generate dynamic live vehicles along corridors based on real lane features
  const vehicles = useMemo(() => {
    const items: Array<{
      id: string
      x1: number
      y1: number
      x2: number
      y2: number
      speed: number
      color: string
      offsetPercent: number
      duration: number
    }> = []

    const corridors = [
      { from: NODES.I1, to: NODES.I2, count: (vI1.totalVehicles + vI2.totalVehicles) || 2, speed: (vI1.meanSpeed + vI2.meanSpeed) / 2 || 8, yOffset: -8 },
      { from: NODES.I2, to: NODES.I1, count: (vI1.totalVehicles + vI2.totalVehicles) || 2, speed: (vI1.meanSpeed + vI2.meanSpeed) / 2 || 8, yOffset: 8 },
      { from: NODES.I1, to: NODES.I3, count: (vI1.totalVehicles + vI3.totalVehicles) || 2, speed: (vI1.meanSpeed + vI3.meanSpeed) / 2 || 8, xOffset: 8 },
      { from: NODES.I3, to: NODES.I1, count: (vI1.totalVehicles + vI3.totalVehicles) || 2, speed: (vI1.meanSpeed + vI3.meanSpeed) / 2 || 8, xOffset: -8 },
      { from: NODES.I2, to: NODES.I4, count: (vI2.totalVehicles + vI4.totalVehicles) || 2, speed: (vI2.meanSpeed + vI4.meanSpeed) / 2 || 8, xOffset: 8 },
      { from: NODES.I4, to: NODES.I2, count: (vI2.totalVehicles + vI4.totalVehicles) || 2, speed: (vI2.meanSpeed + vI4.meanSpeed) / 2 || 8, xOffset: -8 },
      { from: NODES.I3, to: NODES.I4, count: (vI3.totalVehicles + vI4.totalVehicles) || 2, speed: (vI3.meanSpeed + vI4.meanSpeed) / 2 || 8, yOffset: 8 },
      { from: NODES.I4, to: NODES.I3, count: (vI3.totalVehicles + vI4.totalVehicles) || 2, speed: (vI3.meanSpeed + vI4.meanSpeed) / 2 || 8, yOffset: -8 },
    ]

    let idx = 0
    for (const c of corridors) {
      const activeCount = Math.min(Math.max(1, Math.round(c.count / 3)), 5)
      const duration = Math.max(2.5, Math.min(10, 35 / (c.speed || 6)))
      for (let i = 0; i < activeCount; i++) {
        const xOffset = c.xOffset ?? 0
        const yOffset = c.yOffset ?? 0
        items.push({
          id: `veh-${idx++}`,
          x1: c.from.x + xOffset,
          y1: c.from.y + yOffset,
          x2: c.to.x + xOffset,
          y2: c.to.y + yOffset,
          speed: c.speed,
          color: c.speed < 5 ? '#f59e0b' : '#38bdf8',
          offsetPercent: (i / activeCount) * 100,
          duration,
        })
      }
    }
    return items
  }, [
    vI1.totalVehicles,
    vI1.meanSpeed,
    vI2.totalVehicles,
    vI2.meanSpeed,
    vI3.totalVehicles,
    vI3.meanSpeed,
    vI4.totalVehicles,
    vI4.meanSpeed,
  ])

  return (

    <div className="traffic-map-container" aria-label="Interactive 2D Traffic Map">
      {/* Top Map Quick Action Bar for Instant Congestion Demo */}
      <div className="map-action-bar">
        <div className="map-action-title">
          <span className="live-dot" /> CONGESTION DEMO CONTROLLER:
        </div>
        <button
          className="map-ctrl-btn surge-btn"
          onClick={() => onInjectCongestion?.('I2')}
          title="Simulate sudden traffic surge to build critical congestion at I2"
        >
          🔴 Surge Traffic into I2 (Build Congestion)
        </button>
        <button
          className="map-ctrl-btn resolve-btn"
          onClick={() => onResolveCongestion?.('I2')}
          title="Apply AI adaptive signal timing extension to clear the bottleneck"
        >
          ⚡ Prevent Congestion (AI Adaptive Green)
        </button>
        <button
          className="map-ctrl-btn timer-btn"
          onClick={() => onAdjustTimer?.(selectedJunctionId, (visuals[selectedJunctionId]?.greenRemaining || 30) + 15)}
          title="Directly extend green timer by +15s"
        >
          ⏱ +15s Green on {selectedJunctionId}
        </button>
      </div>

      <svg
        className="traffic-map-svg"
        viewBox="0 0 900 560"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Cyber Grid Pattern */}
          <pattern id="gridPattern" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(0, 240, 255, 0.04)" strokeWidth="1" />
          </pattern>

          {/* Glow Filters */}
          <filter id="cyanGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          <filter id="criticalGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          <filter id="signalGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          {/* Linear Gradients for Corridors */}
          <linearGradient id="corridor-h-top" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={statusColor(vI1.status)} stopOpacity="0.4" />
            <stop offset="100%" stopColor={statusColor(vI2.status)} stopOpacity="0.4" />
          </linearGradient>

          <linearGradient id="corridor-h-bot" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={statusColor(vI3.status)} stopOpacity="0.4" />
            <stop offset="100%" stopColor={statusColor(vI4.status)} stopOpacity="0.4" />
          </linearGradient>

          <linearGradient id="corridor-v-left" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={statusColor(vI1.status)} stopOpacity="0.4" />
            <stop offset="100%" stopColor={statusColor(vI3.status)} stopOpacity="0.4" />
          </linearGradient>

          <linearGradient id="corridor-v-right" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={statusColor(vI2.status)} stopOpacity="0.4" />
            <stop offset="100%" stopColor={statusColor(vI4.status)} stopOpacity="0.4" />
          </linearGradient>
        </defs>

        {/* Background Grid */}
        <rect width="900" height="560" fill="#070d18" />
        <rect width="900" height="560" fill="url(#gridPattern)" />

        {/* Outer City Boundary Decor */}
        <rect x="25" y="25" width="850" height="510" rx="8" fill="none" stroke="rgba(0, 240, 255, 0.08)" strokeWidth="1" strokeDasharray="4 8" />

        {/* ========================================================== */}
        {/* EXTERNAL APPROACH ROADS (Extending out of perimeter)       */}
        {/* ========================================================== */}
        {/* North of I1 & I2 */}
        <rect x="212" y="25" width="36" height="125" fill="#0f172a" stroke="#1e293b" strokeWidth="1.5" />
        <rect x="652" y="25" width="36" height="125" fill={vI2.status === 'critical' ? '#2d0f14' : '#0f172a'} stroke={vI2.status === 'critical' ? '#ef4444' : '#1e293b'} strokeWidth="1.5" />
        {/* South of I3 & I4 */}
        <rect x="212" y="410" width="36" height="125" fill="#0f172a" stroke="#1e293b" strokeWidth="1.5" />
        <rect x="652" y="410" width="36" height="125" fill="#0f172a" stroke="#1e293b" strokeWidth="1.5" />
        {/* West of I1 & I3 */}
        <rect x="25" y="132" width="205" height="36" fill="#0f172a" stroke="#1e293b" strokeWidth="1.5" />
        <rect x="25" y="392" width="205" height="36" fill="#0f172a" stroke="#1e293b" strokeWidth="1.5" />
        {/* East of I2 & I4 */}
        <rect x="670" y="132" width="205" height="36" fill={vI2.status === 'critical' ? '#2d0f14' : '#0f172a'} stroke={vI2.status === 'critical' ? '#ef4444' : '#1e293b'} strokeWidth="1.5" />
        <rect x="670" y="392" width="205" height="36" fill="#0f172a" stroke="#1e293b" strokeWidth="1.5" />

        {/* ========================================================== */}
        {/* INTERNAL CORRIDORS (4-way Grid)                            */}
        {/* ========================================================== */}
        {/* Top Corridor: I1 - I2 */}
        <g className="corridor">
          <rect x="230" y="132" width="440" height="36" fill="#0f1b2b" stroke="#1e3a5f" strokeWidth="2" />
          <rect x="230" y="134" width="440" height="32" fill="url(#corridor-h-top)" />
          {/* Lane Divider */}
          <line x1="230" y1="150" x2="670" y2="150" stroke="#00f0ff" strokeWidth="1.5" strokeDasharray="8 6" opacity="0.6" />
          {/* Status glow border */}
          <line x1="230" y1="132" x2="670" y2="132" stroke={corridorStatus('I1', 'I2')} strokeWidth="2.5" opacity="0.8" />
          <line x1="230" y1="168" x2="670" y2="168" stroke={corridorStatus('I1', 'I2')} strokeWidth="2.5" opacity="0.8" />
          <text x="450" y="124" fill="#64748b" fontSize="10" fontFamily="monospace" textAnchor="middle" letterSpacing="1">
            CORRIDOR I1–I2 (MAIN ARTERY NORTH)
          </text>
        </g>

        {/* Bottom Corridor: I3 - I4 */}
        <g className="corridor">
          <rect x="230" y="392" width="440" height="36" fill="#0f1b2b" stroke="#1e3a5f" strokeWidth="2" />
          <rect x="230" y="394" width="440" height="32" fill="url(#corridor-h-bot)" />
          {/* Lane Divider */}
          <line x1="230" y1="410" x2="670" y2="410" stroke="#00f0ff" strokeWidth="1.5" strokeDasharray="8 6" opacity="0.6" />
          <line x1="230" y1="392" x2="670" y2="392" stroke={corridorStatus('I3', 'I4')} strokeWidth="2.5" opacity="0.8" />
          <line x1="230" y1="428" x2="670" y2="428" stroke={corridorStatus('I3', 'I4')} strokeWidth="2.5" opacity="0.8" />
          <text x="450" y="444" fill="#64748b" fontSize="10" fontFamily="monospace" textAnchor="middle" letterSpacing="1">
            CORRIDOR I3–I4 (MAIN ARTERY SOUTH)
          </text>
        </g>

        {/* Left Corridor: I1 - I3 */}
        <g className="corridor">
          <rect x="212" y="150" width="36" height="260" fill="#0f1b2b" stroke="#1e3a5f" strokeWidth="2" />
          <rect x="214" y="150" width="32" height="260" fill="url(#corridor-v-left)" />
          {/* Lane Divider */}
          <line x1="230" y1="150" x2="230" y2="410" stroke="#00f0ff" strokeWidth="1.5" strokeDasharray="8 6" opacity="0.6" />
          <line x1="212" y1="150" x2="212" y2="410" stroke={corridorStatus('I1', 'I3')} strokeWidth="2.5" opacity="0.8" />
          <line x1="248" y1="150" x2="248" y2="410" stroke={corridorStatus('I1', 'I3')} strokeWidth="2.5" opacity="0.8" />
        </g>

        {/* Right Corridor: I2 - I4 */}
        <g className="corridor">
          <rect x="652" y="150" width="36" height="260" fill="#0f1b2b" stroke="#1e3a5f" strokeWidth="2" />
          <rect x="654" y="150" width="32" height="260" fill="url(#corridor-v-right)" />
          {/* Lane Divider */}
          <line x1="670" y1="150" x2="670" y2="410" stroke="#00f0ff" strokeWidth="1.5" strokeDasharray="8 6" opacity="0.6" />
          <line x1="652" y1="150" x2="652" y2="410" stroke={corridorStatus('I2', 'I4')} strokeWidth="2.5" opacity="0.8" />
          <line x1="688" y1="150" x2="688" y2="410" stroke={corridorStatus('I2', 'I4')} strokeWidth="2.5" opacity="0.8" />
        </g>

        {/* ========================================================== */}
        {/* LIVE ANIMATED VEHICLES (CRUISING)                          */}
        {/* ========================================================== */}
        <g className="vehicles-layer">
          {vehicles.map((v) => (
            <g key={v.id}>
              <circle r="4" fill={v.color} filter="url(#cyanGlow)" opacity="0.9">
                <animateMotion
                  path={`M ${v.x1} ${v.y1} L ${v.x2} ${v.y2}`}
                  dur={`${v.duration}s`}
                  repeatCount="indefinite"
                  begin={`-${(v.offsetPercent / 100) * v.duration}s`}
                />
              </circle>
            </g>
          ))}
        </g>

        {/* ========================================================== */}
        {/* QUEUED VEHICLES AT CONGESTED INTERSECTIONS (STOPPED)       */}
        {/* ========================================================== */}
        {Object.entries(NODES).map(([id, node]) => {
          const vis = visuals[id]
          if (vis.queue <= 0) return null

          // Draw stacked red vehicles bumper-to-bumper waiting at the stop line
          const queueCount = Math.min(vis.queue, 8)
          const queueCars = []
          for (let i = 0; i < queueCount; i++) {
            queueCars.push(
              <g key={`queue-${id}-${i}`} transform={`translate(${node.x - 45 - i * 16}, ${node.y - 8})`}>
                <rect width="12" height="7" rx="2" fill="#ef4444" stroke="#f87171" strokeWidth="1" />
                {/* Brake lights */}
                <circle cx="1" cy="2" r="1" fill="#fee2e2" />
                <circle cx="1" cy="5" r="1" fill="#fee2e2" />
              </g>
            )
          }

          return (
            <g key={`queue-group-${id}`}>
              {queueCars}
              {/* Pulsing warning aura when congested */}
              <circle
                cx={node.x}
                cy={node.y}
                r="52"
                fill="none"
                stroke="#ef4444"
                strokeWidth="2.5"
                strokeDasharray="6 4"
                filter="url(#criticalGlow)"
              >
                <animate attributeName="r" values="46;58;46" dur="1.2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.3;0.9" dur="1.2s" repeatCount="indefinite" />
              </circle>
              {/* Congested Floating Badge */}
              <g transform={`translate(${node.x}, ${node.y - 68})`}>
                <rect x="-65" y="-10" width="130" height="20" rx="4" fill="rgba(239, 68, 68, 0.25)" stroke="#ef4444" strokeWidth="1.5" />
                <text y="4" fill="#fecaca" fontSize="9.5" fontFamily="monospace" fontWeight="bold" textAnchor="middle">
                  ⚠️ CONGESTED ({vis.queue} QUEUED)
                </text>
              </g>
            </g>
          )
        })}

        {/* ========================================================== */}
        {/* ROUTE HIGHLIGHTING / AI REROUTE OVERLAY                    */}
        {/* ========================================================== */}
        {latestIntervention && (
          <g className="ai-overlay">
            <path
              d="M 230 150 L 670 150 L 670 410"
              fill="none"
              stroke="#00f0ff"
              strokeWidth="4"
              strokeDasharray="10 8"
              filter="url(#cyanGlow)"
              opacity="0.85"
            >
              <animate attributeName="stroke-dashoffset" values="36;0" dur="1s" repeatCount="indefinite" />
            </path>
            <g transform="translate(450, 75)">
              <rect x="-80" y="-12" width="160" height="24" rx="4" fill="rgba(0, 240, 255, 0.25)" stroke="#00f0ff" strokeWidth="1.5" filter="url(#cyanGlow)" />
              <text y="4" fill="#00f0ff" fontSize="10" fontFamily="monospace" fontWeight="bold" textAnchor="middle">
                ⚡ AI DIVERSION & GREEN EXTENSION
              </text>
            </g>
          </g>
        )}

        {/* ========================================================== */}
        {/* INTERSECTION HUBS (I1, I2, I3, I4)                         */}
        {/* ========================================================== */}
        {Object.entries(NODES).map(([id, node]) => {
          const vis = visuals[id]
          const isSelected = selectedJunctionId === id
          const isInterventionTarget = latestIntervention?.target === id
          const ringColor = statusColor(vis.status)

          // Signal phase colors
          const phase = vis.phase ?? 'GREEN'
          const redActive = phase === 'RED'
          const yellowActive = phase === 'YELLOW'
          const greenActive = phase === 'GREEN'

          return (
            <g
              key={id}
              className={`intersection-node ${isSelected ? 'selected' : ''}`}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onSelectJunction(id)}
              style={{ cursor: 'pointer' }}
            >
              {/* Target Selection Pulse Ring */}
              {isSelected && (
                <circle r="46" fill="none" stroke="#00f0ff" strokeWidth="2" strokeDasharray="6 4" opacity="0.85">
                  <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="12s" repeatCount="indefinite" />
                </circle>
              )}

              {/* Congestion Perimeter Ring */}
              <circle r="36" fill="#091424" stroke={ringColor} strokeWidth={isSelected ? 3 : 2} filter="url(#cyanGlow)" />
              <circle r="30" fill="#0d1b2e" />

              {/* Junction ID & Name */}
              <text y="-6" fill="#f8fafc" fontSize="14" fontWeight="800" fontFamily="monospace" textAnchor="middle">
                {id}
              </text>
              <text y="10" fill={vis.queue > 0 ? '#f87171' : '#94a3b8'} fontSize="8.5" fontFamily="monospace" fontWeight={vis.queue > 0 ? 'bold' : 'normal'} textAnchor="middle">
                {vis.queue > 0 ? `QUEUE: ${vis.queue}` : 'CLEAR'}
              </text>

              {/* Status Dot */}
              <circle cx="0" cy="18" r="3" fill={ringColor} />

              {/* TRAFFIC SIGNALS (Four Approach Heads around Intersection) */}
              {/* North Signal Head */}
              <g transform="translate(0, -48)">
                <rect x="-16" y="-7" width="32" height="14" rx="3" fill="#020617" stroke="#1e293b" strokeWidth="1" />
                <circle cx="-9" cy="0" r="3" fill={redActive ? '#ef4444' : '#450a0a'} filter={redActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="0" cy="0" r="3" fill={yellowActive ? '#f59e0b' : '#451a03'} filter={yellowActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="9" cy="0" r="3" fill={greenActive ? '#10b981' : '#022c22'} filter={greenActive ? 'url(#signalGlow)' : undefined} />
              </g>

              {/* East Signal Head */}
              <g transform="translate(48, 0) rotate(90)">
                <rect x="-16" y="-7" width="32" height="14" rx="3" fill="#020617" stroke="#1e293b" strokeWidth="1" />
                <circle cx="-9" cy="0" r="3" fill={redActive ? '#ef4444' : '#450a0a'} filter={redActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="0" cy="0" r="3" fill={yellowActive ? '#f59e0b' : '#451a03'} filter={yellowActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="9" cy="0" r="3" fill={greenActive ? '#10b981' : '#022c22'} filter={greenActive ? 'url(#signalGlow)' : undefined} />
              </g>

              {/* South Signal Head */}
              <g transform="translate(0, 48)">
                <rect x="-16" y="-7" width="32" height="14" rx="3" fill="#020617" stroke="#1e293b" strokeWidth="1" />
                <circle cx="-9" cy="0" r="3" fill={redActive ? '#ef4444' : '#450a0a'} filter={redActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="0" cy="0" r="3" fill={yellowActive ? '#f59e0b' : '#451a03'} filter={yellowActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="9" cy="0" r="3" fill={greenActive ? '#10b981' : '#022c22'} filter={greenActive ? 'url(#signalGlow)' : undefined} />
              </g>

              {/* West Signal Head */}
              <g transform="translate(-48, 0) rotate(90)">
                <rect x="-16" y="-7" width="32" height="14" rx="3" fill="#020617" stroke="#1e293b" strokeWidth="1" />
                <circle cx="-9" cy="0" r="3" fill={redActive ? '#ef4444' : '#450a0a'} filter={redActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="0" cy="0" r="3" fill={yellowActive ? '#f59e0b' : '#451a03'} filter={yellowActive ? 'url(#signalGlow)' : undefined} />
                <circle cx="9" cy="0" r="3" fill={greenActive ? '#10b981' : '#022c22'} filter={greenActive ? 'url(#signalGlow)' : undefined} />
              </g>

              {/* LIVE TRAFFIC SIGNAL TIMER BADGE (Active countdown) */}
              <g transform="translate(0, 64)">
                <rect
                  x="-36"
                  y="-9"
                  width="72"
                  height="18"
                  rx="4"
                  fill="rgba(15, 23, 42, 0.95)"
                  stroke={greenActive ? '#10b981' : redActive ? '#ef4444' : '#f59e0b'}
                  strokeWidth="1.5"
                />
                <text
                  y="4"
                  fill={greenActive ? '#34d399' : redActive ? '#f87171' : '#fbbf24'}
                  fontSize="9.5"
                  fontFamily="monospace"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  {phase === 'GREEN' ? '🟢' : phase === 'RED' ? '🔴' : '🟡'} {vis.greenRemaining !== null ? `${vis.greenRemaining.toFixed(0)}s` : '--'}
                </text>
              </g>

              {/* +15s Quick Signal Timer Adjustment Button */}
              <g
                transform="translate(48, 64)"
                onClick={(e) => {
                  e.stopPropagation()
                  onAdjustTimer?.(id, (vis.greenRemaining || 30) + 15)
                }}
                style={{ cursor: 'pointer' }}
              >
                <title>{`Extend ${id} Green Duration by +15s`}</title>
                <rect x="-14" y="-8" width="28" height="16" rx="3" fill="#0284c7" stroke="#38bdf8" strokeWidth="1" />
                <text y="4" fill="#fff" fontSize="8.5" fontFamily="monospace" fontWeight="bold" textAnchor="middle">
                  +15s
                </text>
              </g>


              {/* AI Actuation Indicator Tag */}
              {isInterventionTarget && (
                <g transform="translate(0, -66)">
                  <rect x="-44" y="-9" width="88" height="18" rx="4" fill="rgba(0, 240, 255, 0.25)" stroke="#00f0ff" strokeWidth="1.2" filter="url(#cyanGlow)" />
                  <text y="4" fill="#00f0ff" fontSize="8" fontFamily="monospace" fontWeight="bold" textAnchor="middle">
                    AI ADAPTED ({latestIntervention.applied_duration}s)
                  </text>
                </g>
              )}
            </g>
          )
        })}

        {/* Map Legend Overlay */}
        <g transform="translate(40, 500)">
          <rect width="360" height="34" rx="4" fill="rgba(8, 14, 26, 0.9)" stroke="rgba(0, 240, 255, 0.15)" strokeWidth="1" />
          <circle cx="20" cy="17" r="5" fill="#00f0a0" />
          <text x="32" y="21" fill="#94a3b8" fontSize="10" fontFamily="monospace">Flowing</text>
          <circle cx="95" cy="17" r="5" fill="#f59e0b" />
          <text x="107" y="21" fill="#94a3b8" fontSize="10" fontFamily="monospace">Moderate</text>
          <circle cx="180" cy="17" r="5" fill="#ef4444" />
          <text x="192" y="21" fill="#f87171" fontSize="10" fontFamily="monospace" fontWeight="bold">Congested</text>
          <circle cx="270" cy="17" r="5" fill="#00f0ff" />
          <text x="282" y="21" fill="#00f0ff" fontSize="10" fontFamily="monospace">AI Route</text>
        </g>
      </svg>
    </div>
  )
})
