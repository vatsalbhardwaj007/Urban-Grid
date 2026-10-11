import { selectIntersectionVisual } from '../../selectors/trafficVisuals'
import { TrafficMap2D } from '../DigitalTwin/TrafficMap2D'
import type { Junction } from '../../types/digitalTwin'
import { isRouteActuationResult, isSignalActuationResult } from '../../types/traffic'
import type { ControlLoopStatus, SignalActuationResult, TrafficSnapshot, TrafficState, VehicleState } from '../../types/traffic'
import type { ConnectionStatus, ControlCycleSummary } from '../../state/trafficStore'
import { Icon } from '../Icon'
import { ManualSignalControl } from './ManualSignalControl'
import { ActionHistory } from './ActionHistory'

type Props = { junction: Junction; traffic: TrafficState | undefined; allTraffic: TrafficSnapshot; availableJunctions: Junction[]; loopStatus: ControlLoopStatus | null; controlMode: ControlLoopStatus['mode'] | null; health: import('../../types/traffic').HealthResponse | null; intersectionAvailable: boolean; actionHistory: import('../../state/trafficStore').ActionHistoryRecord[]; latestIntervention: SignalActuationResult | null; lastControlCycle: ControlCycleSummary | null; status: ConnectionStatus; onSelectJunction: (id: string) => void; onApplyManualSignal: (target: string, duration: number) => Promise<SignalActuationResult>; selectedVehicle?: VehicleState; onFollowVehicle: () => void; onClearVehicle: () => void }

const feedLabel = (status: ConnectionStatus) => status === 'connected' ? 'LIVE' : status.replace('-', ' ').toUpperCase()
function actionSummary(action: Record<string, unknown>) {
  if (isSignalActuationResult(action)) return `${action.target}: ${action.applied_duration.toFixed(1)}s ${action.current_phase.toLowerCase()} phase · ${action.source.toLowerCase()} source`
  if (isRouteActuationResult(action)) return `${action.target}: ${action.applied_route.length} route edge${action.applied_route.length === 1 ? '' : 's'} · ${action.source.toLowerCase()} source`
  const target = typeof action.target === 'string' ? action.target : 'Unknown target'
  const message = typeof action.message === 'string' ? action.message : 'Backend returned an untyped action result.'
  return `${target}: ${message}`
}

export function ContextPanel({ junction, traffic, allTraffic, availableJunctions, loopStatus, controlMode, health, intersectionAvailable, actionHistory, latestIntervention, lastControlCycle, status, onSelectJunction, onApplyManualSignal, selectedVehicle, onFollowVehicle, onClearVehicle }: Props) {
  if (selectedVehicle) return <aside className="context-panel vehicle-context" aria-label="Selected real SUMO vehicle">
    <div className="context-head"><span className="panel-label">VEHICLE INTELLIGENCE</span><button className="context-icon" aria-label="Close vehicle details" onClick={onClearVehicle}>×</button></div>
    <div className="intersection-title"><span className="intersection-id">V</span><div><h1>{selectedVehicle.id}</h1><p>{status === 'connected' ? 'Live SUMO vehicle' : 'Last real SUMO vehicle snapshot'}</p></div></div>
    <div className="intersection-meta"><span className="traffic-status"><i className="traffic-dot" />{selectedVehicle.speed.toFixed(1)} m/s</span><span className={`feed-state connection-${status}`}>{feedLabel(status)}</span></div>
    <section className="intel-card"><div className="intel-title"><span>{status === 'connected' ? 'Real-time state' : 'Last observed state'}</span><Icon name="activity" size={16} /></div>
      <dl className="metric-grid"><div><dt>Speed</dt><dd>{selectedVehicle.speed.toFixed(1)}<small>m/s</small></dd></div><div><dt>Heading</dt><dd>{selectedVehicle.angle.toFixed(0)}<small>° SUMO</small></dd></div><div><dt>Lane</dt><dd className="vehicle-code">{selectedVehicle.lane_id || '—'}</dd></div><div><dt>Road</dt><dd className="vehicle-code">{selectedVehicle.road_id ?? '—'}</dd></div></dl>
      <p className="metric-explanation">Direct TraCI snapshot. Position is rendered in the 3D scene; no route or prediction is inferred.</p>
    </section>
    <section className="intel-card"><div className="intel-title"><span>Vehicle type</span><span className="panel-label">SUMO</span></div><strong className="vehicle-type">{selectedVehicle.vehicle_type ?? 'Unknown type'}</strong><button className="step-button vehicle-follow-button" disabled={status !== 'connected'} onClick={onFollowVehicle}><Icon name="followVehicle" size={16} /><span>Follow vehicle</span><span className="step-arrow"><Icon name="arrow" size={14} /></span></button></section>
    <div className="data-provenance"><span className="panel-label">DATA SOURCE</span><p>SUMO / TraCI · stable ID {selectedVehicle.id}</p><span>Real vehicle state · no synthetic movement</span></div>
  </aside>
  const visual = selectIntersectionVisual(traffic)
  const lanes = traffic?.lane_features ?? []
  const peakCount = Math.max(1, ...lanes.map((lane) => lane.vehicle_count))
  const intervention = latestIntervention?.target === junction.id ? latestIntervention : null
  return <aside className={`context-panel status-${visual.status}`} aria-label="Selected intersection telemetry">
    <div className="context-head"><span className="panel-label">INTERSECTION INTELLIGENCE</span><span className="context-icon"><Icon name="junction" /></span></div>
    <div className="intersection-title"><span className="intersection-id">{junction.id}</span><div><h1>{junction.name}</h1><p>Monitored intersection</p></div></div>
    <div className="intersection-meta"><span className="traffic-status"><i className="traffic-dot" />{traffic ? visual.status === 'flowing' ? 'Flowing traffic' : visual.status === 'moderate' ? 'Moderate traffic' : 'Critical traffic' : 'Awaiting telemetry'}</span><span className={`feed-state connection-${status}`}>{feedLabel(status)}</span></div>
    <nav className="junction-options" aria-label="Select intersection">{availableJunctions.map((item) => <button className={`${item.id === junction.id ? 'active' : ''} status-${selectIntersectionVisual(allTraffic[item.id]).status}`} key={item.id} aria-pressed={item.id === junction.id} onClick={() => onSelectJunction(item.id)} title={`Focus ${item.id} ${item.name}`}><i className="traffic-dot" />{item.id}</button>)}</nav>
    <TrafficMap2D trafficByIntersection={allTraffic} status={status} selectedJunctionId={junction.id} onSelectJunction={onSelectJunction} />
    <section className="intel-card"><div className="intel-title"><span>Traffic overview</span><Icon name="activity" size={16} /></div><div className="primary-metric"><strong>{traffic ? visual.totalVehicles : '—'}</strong><span>vehicles observed<small>across {traffic ? lanes.length : '—'} approach lanes</small></span></div>
      <dl className="metric-grid"><div><dt>Mean speed</dt><dd>{traffic ? visual.meanSpeed.toFixed(1) : '—'}<small>m/s</small></dd></div><div><dt>Queue length</dt><dd>{traffic ? visual.queue : '—'}<small>vehicles</small></dd></div><div><dt>Density</dt><dd>{traffic ? visual.density.toFixed(1) : '—'}<small>veh/km</small></dd></div><div><dt>Arrival rate</dt><dd>{traffic ? traffic.arrival_rate.toFixed(2) : '—'}<small>veh/s</small></dd></div></dl>
      <div className="congestion-heading"><span>Congestion index</span><b>{traffic ? `${visual.congestion}%` : '—'}</b></div><div className="congestion-track"><i style={{ width: `${traffic ? visual.congestion : 0}%` }} /></div><p className="metric-explanation">Derived from queue, density and speed. Not an AI prediction.</p>
    </section>
    <section className="intel-card signal-card"><div className="intel-title"><span>Traffic signal</span><span className="panel-label">{loopStatus?.mode ?? '—'}</span></div><div className="signal-detail"><div className="signal-housing" aria-label={`Signal ${visual.phase ?? 'unknown'}`}>{(['RED','YELLOW','GREEN'] as const).map((phase) => <i key={phase} className={visual.phase === phase ? `lit ${phase.toLowerCase()}` : ''} />)}</div><div><b className={`phase-${visual.phase?.toLowerCase() ?? 'unknown'}`}>{visual.phase ?? 'No signal data'}</b><span>{visual.greenRemaining === null ? 'Awaiting backend state' : `${visual.greenRemaining.toFixed(1)}s green remaining`}</span></div></div>{intervention && <p className="intervention-note">{intervention.message}</p>}</section>
    <ManualSignalControl intersectionId={junction.id} intersectionAvailable={intersectionAvailable} traffic={traffic} health={health} status={status} mode={controlMode} onApply={onApplyManualSignal} />
    <ActionHistory records={actionHistory} />
    <section className="intel-card prevention-card"><div className="intel-title"><span>Prevent before congestion</span><span className="panel-label">LIVE API</span></div>
      <p className="prevention-copy">This backend exposes the closed-loop decision run, but not a prediction probability, horizon, or separate prevention scenario. The congestion index above is descriptive only.</p>
      {lastControlCycle ? <div className={`cycle-result ${lastControlCycle.success ? 'successful' : 'failed'}`}><span>{lastControlCycle.success ? 'Last cycle confirmed' : 'Last cycle reported errors'}</span><b>#{lastControlCycle.cycle} · {lastControlCycle.actionsAttempted} action{lastControlCycle.actionsAttempted === 1 ? '' : 's'}</b>{lastControlCycle.actionResults.length > 0 && <div className="action-result-list">{lastControlCycle.actionResults.map((action, index) => <div className="action-result" key={`${lastControlCycle.cycle}-${index}`}><span>{action.success === true ? 'Confirmed action' : action.success === false ? 'Failed action' : 'Backend action result'}</span><small>{actionSummary(action)}</small></div>)}</div>}{lastControlCycle.errors.map((error, index) => <small key={`${lastControlCycle.cycle}-error-${index}`}>{error}</small>)}</div> : <div className="cycle-result"><span>No control cycle run in this session</span><b>Use “Step control loop” to execute the existing policy.</b></div>}
      {intervention && intervention.success && <p className="intervention-note">Applied at {intervention.target}: {intervention.applied_duration.toFixed(1)}s {intervention.current_phase.toLowerCase()} phase ({intervention.source.toLowerCase()} source).</p>}
    </section>
    <section className="intel-card lane-card"><div className="intel-title"><span>Lane observations</span><span className="panel-label">VEHICLES</span></div><div className="lane-list">{lanes.length ? lanes.map((lane) => <div className="lane-observation" key={lane.lane_id} title={`${lane.lane_id}: ${lane.vehicle_count} vehicles, ${lane.queue_length} queued`}><span>{lane.lane_id}</span><div className="lane-meter"><i style={{width:`${lane.vehicle_count / peakCount * 100}%`}} /><em style={{width:`${Math.min(lane.queue_length, lane.vehicle_count) / peakCount * 100}%`}} /></div><b>{lane.vehicle_count}</b></div>) : <div className="empty-telemetry">Lane observations will appear when the backend sends traffic data.</div>}</div><div className="lane-legend"><span><i/>Observed</span><span><i/>Queued</span></div></section>
    <div className="data-provenance"><span className="panel-label">DATA SOURCE</span><p>SUMO / TraCI · {traffic ? `Simulation ${traffic.timestamp.toFixed(1)}s` : 'Awaiting connection'}</p><span>Aggregate intersection telemetry</span></div>
  </aside>
}
