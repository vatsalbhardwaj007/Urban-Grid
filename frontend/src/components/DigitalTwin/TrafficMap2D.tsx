/* oxlint-disable react/only-export-components */
import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { urbanGridTopology } from '../../data/urbanGridTopology'
import { selectIntersectionVisual, selectRoadStatus } from '../../selectors/trafficVisuals'
import type { ConnectionStatus } from '../../state/trafficStore'
import type { Junction, Road, TrafficVisualStatus } from '../../types/digitalTwin'
import type { SignalPhase, TrafficSnapshot, TrafficState } from '../../types/traffic'

export const TRAFFIC_MAP_VIEW_BOX = '0 0 320 224'

export type TrafficMapPoint = { id: string; name: string; x: number; y: number }
export type TrafficMapRoad = { id: string; from: TrafficMapPoint; to: TrafficMapPoint; status: TrafficVisualStatus }

const MAP_PADDING = 44
const MAP_WIDTH = 320
const MAP_HEIGHT = 224

export function signalColor(phase: SignalPhase | null) {
  if (phase === 'GREEN') return '#76d9ad'
  if (phase === 'YELLOW') return '#e9b765'
  if (phase === 'RED') return '#ed8278'
  return '#789099'
}

export function trafficMapTelemetry(state: TrafficState | undefined, connection: ConnectionStatus) {
  const visual = selectIntersectionVisual(state)
  const unavailable = !state || connection === 'backend-unavailable' || connection === 'sumo-unavailable'
  return {
    ...visual,
    phase: unavailable ? null : visual.phase,
    available: !unavailable,
    stale: connection === 'telemetry-stale' || connection === 'reconnecting',
    source: connection === 'connected' ? 'Live WebSocket' : connection === 'rest-fallback' ? 'REST fallback' : connection === 'telemetry-stale' ? 'Last real snapshot · stale' : connection === 'reconnecting' ? 'Reconnecting · last real snapshot' : connection === 'backend-unavailable' ? 'Backend unavailable' : connection === 'sumo-unavailable' ? 'SUMO unavailable' : 'Awaiting telemetry',
  }
}

/** Converts the same world-space anchors used by the Three.js Twin into SVG coordinates. */
export function trafficMapPoints(junctions: Junction[]): TrafficMapPoint[] {
  const minX = Math.min(...junctions.map((junction) => junction.x))
  const maxX = Math.max(...junctions.map((junction) => junction.x))
  const minZ = Math.min(...junctions.map((junction) => junction.z))
  const maxZ = Math.max(...junctions.map((junction) => junction.z))
  const scaleX = (MAP_WIDTH - MAP_PADDING * 2) / Math.max(1, maxX - minX)
  const scaleY = (MAP_HEIGHT - MAP_PADDING * 2) / Math.max(1, maxZ - minZ)
  return junctions.map((junction) => ({ id: junction.id, name: junction.name, x: MAP_PADDING + (junction.x - minX) * scaleX, y: MAP_PADDING + (maxZ - junction.z) * scaleY }))
}

export function trafficMapRoads(junctions: Junction[], roads: Road[], trafficByIntersection: TrafficSnapshot): TrafficMapRoad[] {
  const points = new Map(trafficMapPoints(junctions).map((point) => [point.id, point]))
  return roads.flatMap((road) => {
    const from = points.get(road.from)
    const to = points.get(road.to)
    return from && to ? [{ id: road.id, from, to, status: selectRoadStatus(road, trafficByIntersection) }] : []
  })
}

/** Kept as the map's activation path so tests cover the same selection callback used by SVG nodes. */
export function activateTrafficMapIntersection(id: string, onSelect: (id: string) => void) { onSelect(id) }

function statusStroke(status: TrafficVisualStatus) {
  return status === 'flowing' ? '#76d9ad' : status === 'moderate' ? '#e9b765' : status === 'critical' ? '#ed8278' : '#526c77'
}

function ZoomIcon({ direction }: { direction: 1 | -1 }) { return <span aria-hidden="true">{direction > 0 ? '+' : '−'}</span> }

export function TrafficMap2D({ trafficByIntersection, status, selectedJunctionId, onSelectJunction }: { trafficByIntersection: TrafficSnapshot; status: ConnectionStatus; selectedJunctionId: string; onSelectJunction: (id: string) => void }) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number } | null>(null)
  const points = useMemo(() => trafficMapPoints(urbanGridTopology.junctions), [])
  const roads = useMemo(() => trafficMapRoads(urbanGridTopology.junctions, urbanGridTopology.roads, trafficByIntersection).map((road) => ({ ...road, status: status === 'backend-unavailable' || status === 'sumo-unavailable' ? 'unknown' as const : road.status })), [status, trafficByIntersection])
  const pointById = useMemo(() => new Map(points.map((point) => [point.id, point])), [points])
  const reset = () => { setZoom(1); setPan({ x: 0, y: 0 }) }
  const changeZoom = (direction: 1 | -1) => setZoom((value) => Math.max(.8, Math.min(1.65, Number((value + direction * .2).toFixed(2)))))
  const onPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    if (event.target !== event.currentTarget) return
    drag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y }
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const active = drag.current
    if (!active || active.pointerId !== event.pointerId) return
    setPan({ x: Math.max(-36, Math.min(36, active.panX + (event.clientX - active.x) / zoom)), y: Math.max(-28, Math.min(28, active.panY + (event.clientY - active.y) / zoom)) })
  }
  const stopDragging = () => { drag.current = null }
  const nodeKeyDown = (event: KeyboardEvent<SVGGElement>, id: string) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activateTrafficMapIntersection(id, onSelectJunction) }
  }
  const transform = `translate(${pan.x} ${pan.y}) translate(160 112) scale(${zoom}) translate(-160 -112)`
  const mapStatus = status === 'telemetry-stale' || status === 'reconnecting' ? 'stale' : status === 'backend-unavailable' || status === 'sumo-unavailable' ? 'unavailable' : 'current'

  return <section className={`traffic-map-card map-${mapStatus}`} aria-label="Synchronized 2D traffic map">
    <header className="traffic-map-header"><div><span className="panel-label">SYNCHRONIZED 2D MAP</span><h3>Network overview</h3></div><span className="traffic-map-source">{status === 'connected' ? 'LIVE' : status === 'rest-fallback' ? 'REST' : status === 'telemetry-stale' ? 'STALE' : status === 'reconnecting' ? 'RECONNECTING' : status === 'connecting' ? 'PENDING' : 'UNAVAILABLE'}</span></header>
    <div className="traffic-map-canvas">
      <svg viewBox={TRAFFIC_MAP_VIEW_BOX} role="group" aria-label="Interactive I1 through I4 traffic network map" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={stopDragging} onPointerCancel={stopDragging}>
        <title>Urban Grid 2D traffic network</title><desc>Use the intersection nodes to synchronize selection with the 3D Digital Twin. Drag empty map space to pan.</desc>
        <g className="traffic-map-grid" aria-hidden="true"><path d="M0 56H320M0 112H320M0 168H320M80 0V224M160 0V224M240 0V224" /></g>
        <g transform={transform}>
          {roads.map((road) => <g key={road.id} className={`traffic-map-road status-${road.status}`} aria-label={`${road.id} ${road.status} congestion`}><line x1={road.from.x} y1={road.from.y} x2={road.to.x} y2={road.to.y} className="traffic-map-road-base" /><line x1={road.from.x} y1={road.from.y} x2={road.to.x} y2={road.to.y} className="traffic-map-road-state" stroke={statusStroke(road.status)} /></g>)}
          {urbanGridTopology.junctions.map((junction) => {
            const point = pointById.get(junction.id)!
            const telemetry = trafficMapTelemetry(trafficByIntersection[junction.id], status)
            const selected = junction.id === selectedJunctionId
            const label = `${junction.id} ${junction.name}. ${telemetry.available ? `${telemetry.queue} queued, ${telemetry.congestion}% congestion, signal ${telemetry.phase ?? 'unavailable'}.` : telemetry.source}`
            return <g key={junction.id} className={`traffic-map-node status-${telemetry.status} ${selected ? 'selected' : ''} ${telemetry.stale ? 'stale' : ''}`} role="button" tabIndex={0} aria-label={label} aria-pressed={selected} onClick={() => activateTrafficMapIntersection(junction.id, onSelectJunction)} onKeyDown={(event) => nodeKeyDown(event, junction.id)}>
              <title>{label}</title><circle cx={point.x} cy={point.y} r="18" className="traffic-map-node-halo" /><circle cx={point.x} cy={point.y} r="12" className="traffic-map-node-core" /><circle cx={point.x + 10} cy={point.y - 10} r="4" fill={signalColor(telemetry.phase)} className="traffic-map-signal" />
              <text x={point.x} y={point.y + 4} textAnchor="middle">{junction.id}</text><text x={point.x} y={point.y + 33} textAnchor="middle" className="traffic-map-queue">{telemetry.available ? `Q ${telemetry.queue}` : 'NO DATA'}</text>
            </g>
          })}
        </g>
      </svg>
      <div className="traffic-map-controls" role="group" aria-label="2D map navigation"><button type="button" onClick={() => changeZoom(1)} aria-label="Zoom in map" title="Zoom in map"><ZoomIcon direction={1} /></button><button type="button" onClick={() => changeZoom(-1)} aria-label="Zoom out map" title="Zoom out map"><ZoomIcon direction={-1} /></button><button type="button" onClick={reset} aria-label="Reset map view" title="Reset city overview">Reset</button></div>
    </div>
    <div className="traffic-map-footer"><span className={`traffic-dot status-${mapStatus === 'current' ? 'flowing' : mapStatus === 'stale' ? 'moderate' : 'unknown'}`} />{status === 'telemetry-stale' || status === 'reconnecting' ? 'Last real telemetry retained; awaiting recovery.' : status === 'backend-unavailable' || status === 'sumo-unavailable' ? 'Map topology remains available; telemetry is unavailable.' : 'Select a node to focus the shared Digital Twin selection.'}</div>
  </section>
}
