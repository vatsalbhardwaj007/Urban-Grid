import { selectIntersectionVisual } from '../../selectors/trafficVisuals'
import type { Junction } from '../../types/digitalTwin'
import type { ControlLoopStatus, SignalActuationResult, TrafficSnapshot, TrafficState } from '../../types/traffic'

type Props = { junction: Junction; traffic: TrafficState | undefined; allTraffic: TrafficSnapshot; availableJunctions: Junction[]; loopStatus: ControlLoopStatus | null; latestIntervention: SignalActuationResult | null }

export function ContextPanel({ junction, traffic, allTraffic, availableJunctions, loopStatus, latestIntervention }: Props) {
  const visual = selectIntersectionVisual(traffic)
  const hasTraffic = Boolean(traffic)
  const nearby = [junction, ...availableJunctions.filter((item) => item.id !== junction.id)].slice(0, 3)
  const lanes = traffic?.lane_features ?? []
  const queueBars = lanes.slice(0, 8).map((lane) => Math.max(4, Math.min(35, lane.queue_length * 7 + lane.vehicle_count * 3)))
  const phaseClass = visual.phase?.toLowerCase() ?? ''
  const intervention = latestIntervention?.target === junction.id ? latestIntervention : null
  return <aside className="context-panel">
    <section className="context-head"><span className="close">×</span><div className="panel-label">M2 CONTEXTUAL TELEMETRY</div><h1>{junction.name}</h1><p>{junction.id} · canonical monitored intersection</p></section>
    <div className="junction-tabs"><span className="dot">●</span><b>{junction.id}</b> selected intersection <span className="chevron">⌄</span></div>
    <div className="junction-options">{nearby.map((item) => { const itemTraffic = allTraffic[item.id]; return <div className={`junction-option ${item.id === junction.id ? 'active' : ''}`} key={item.id}><b>{item.id}</b>{item.name}<br/>{itemTraffic ? `${itemTraffic.total_queue} queued` : 'No data'}</div> })}</div>
    <section className="intel-card"><div className="intel-title">◌　Current traffic <span className="badge">{hasTraffic ? visual.status.toUpperCase() : 'NO DATA'}</span></div><div className="metric"><strong>{hasTraffic ? visual.queue : '—'}</strong><span>total queue<br/>vehicles</span></div><div className="bar-chart">{queueBars.length ? queueBars.map((height, index) => <i key={index} style={{height}} />) : <span className="model">Awaiting lane telemetry</span>}</div><p className="trend">{hasTraffic ? `${visual.totalVehicles} observed across lanes` : 'No canonical traffic state received'} <span>{hasTraffic ? `${visual.meanSpeed.toFixed(1)} m/s` : ''}</span></p></section>
    <section className="intel-card"><div className="intel-title">✧　Live flow telemetry <span className="badge risk">{hasTraffic ? `${visual.density.toFixed(1)} veh/km` : 'NO DATA'}</span></div><div className="metric"><strong className="red-number">{hasTraffic ? `${visual.congestion}%` : '—'}</strong><span>derived congestion<br/>rendering index</span></div><div className="riskline">{hasTraffic && <i style={{marginLeft: `${visual.congestion}%`}} />}</div><p className="model">Arrival {traffic?.arrival_rate.toFixed(2) ?? '—'} veh/s　•　Flow {hasTraffic ? lanes.reduce((total, lane) => total + lane.flow, 0).toFixed(0) : '—'} veh/hr</p></section>
    <section className="intel-card"><div className="intel-title">⌘　Signal & control loop <span className="badge route-badge">{visual.phase ?? 'NO DATA'}</span></div><div className="signal-row"><div className={`signal ${phaseClass}`}><i/>{visual.phase ?? '—'}</div><div className="signal"><i/>{visual.greenRemaining === null ? '—' : `${visual.greenRemaining.toFixed(1)}s`}</div></div><p className="route-reason">{intervention ? intervention.message : loopStatus ? `Loop ${loopStatus.is_running ? 'running' : 'ready'} · ${loopStatus.decision_engine}` : 'No M2 loop telemetry received.'}</p></section>
  </aside>
}
