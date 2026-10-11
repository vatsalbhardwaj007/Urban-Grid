import { memo } from 'react'
import type { HistoryPoint } from '../../state/trafficStore'

interface Props {
  history: HistoryPoint[]
  currentVehicles: number
  currentSpeed: number
  currentQueue: number
  currentDensity: number
}

function Sparkline({
  data,
  color,
  fallbackVal,
}: {
  data: number[]
  color: string
  fallbackVal: number
}) {
  const points = data.length > 0 ? data : [fallbackVal, fallbackVal]
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const width = 160
  const height = 36

  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1 || 1)) * (width - 8) + 4
    const y = height - 4 - ((val - min) / range) * (height - 8)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const pathD = `M ${coords.join(' L ')}`
  const areaD = `${pathD} L ${width - 4},${height} L 4,${height} Z`

  return (
    <svg width={width} height={height} className="sparkline-svg">
      <defs>
        <linearGradient id={`grad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#grad-${color.replace('#', '')})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      {points.length > 0 && (
        <circle
          cx={(coords[coords.length - 1].split(',')[0])}
          cy={(coords[coords.length - 1].split(',')[1])}
          r="3"
          fill={color}
        />
      )}
    </svg>
  )
}

export const TrafficCharts = memo(function TrafficCharts({
  history,
  currentVehicles,
  currentSpeed,
  currentQueue,
  currentDensity,
}: Props) {
  const flowData = history.map((h) => h.flow)
  const speedData = history.map((h) => h.meanSpeed)
  const queueData = history.map((h) => h.totalQueue)
  const densityData = history.map((h) => h.density)

  const latestFlow = history.length > 0 ? history[history.length - 1].flow : currentVehicles * 60

  return (
    <footer className="ug-bottom-analytics" aria-label="Live Network Analytics">
      <div className="analytics-card">
        <div className="analytics-meta">
          <span className="analytics-label">TRAFFIC FLOW</span>
          <span className="analytics-val">{latestFlow} veh/h</span>
        </div>
        <Sparkline data={flowData} color="#00f0ff" fallbackVal={latestFlow} />
      </div>

      <div className="analytics-card">
        <div className="analytics-meta">
          <span className="analytics-label">AVERAGE SPEED</span>
          <span className="analytics-val">{currentSpeed.toFixed(1)} m/s</span>
        </div>
        <Sparkline data={speedData} color="#10b981" fallbackVal={currentSpeed} />
      </div>

      <div className="analytics-card">
        <div className="analytics-meta">
          <span className="analytics-label">QUEUE LENGTH</span>
          <span className="analytics-val" style={{ color: currentQueue > 5 ? '#f87171' : '#f8fafc' }}>
            {currentQueue} veh
          </span>
        </div>
        <Sparkline data={queueData} color="#f59e0b" fallbackVal={currentQueue} />
      </div>

      <div className="analytics-card">
        <div className="analytics-meta">
          <span className="analytics-label">NETWORK DENSITY</span>
          <span className="analytics-val">{currentDensity.toFixed(1)} veh/km</span>
        </div>
        <Sparkline data={densityData} color="#818cf8" fallbackVal={currentDensity} />
      </div>
    </footer>
  )
})
