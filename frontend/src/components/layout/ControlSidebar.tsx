import { useState } from 'react'
import { viewModes } from '../../data/viewModes'
import { urbanGridTopology } from '../../data/urbanGridTopology'
import { selectIntersectionVisual } from '../../selectors/trafficVisuals'
import type { ControlLoopStatus, TrafficSnapshot } from '../../types/traffic'
import type { ViewMode } from '../../types/digitalTwin'
import { Icon } from '../Icon'

type Props = { viewMode: ViewMode; selectedJunctionId: string; onModeChange: (mode: ViewMode) => void; onSelectJunction: (id: string) => void; onStepAiLoop: () => Promise<void>; stepDisabled: boolean; loopStatus: ControlLoopStatus | null; trafficByIntersection: TrafficSnapshot }

export function ControlSidebar({ viewMode, selectedJunctionId, onModeChange, onSelectJunction, onStepAiLoop, stepDisabled, loopStatus, trafficByIntersection }: Props) {
  const [stepping, setStepping] = useState(false)
  const step = async () => { setStepping(true); try { await onStepAiLoop() } finally { setStepping(false) } }
  return <aside className="control-sidebar" aria-label="Monitoring controls">
    <div className="sidebar-heading"><span className="panel-label">WORKSPACE</span><span className="workspace-number">01</span></div>
    <div className="mode-list">{viewModes.map((mode) => <button key={mode.id} className={`mode-button ${viewMode === mode.id ? 'active' : ''}`} aria-pressed={viewMode === mode.id} disabled={mode.disabled} title={mode.description} onClick={() => onModeChange(mode.id)}><Icon name={mode.id} /><span>{mode.label}</span>{mode.disabled && <span className="unavailable-mark">—</span>}</button>)}</div>
    <div className="side-rule" />
    <div className="sidebar-heading"><span className="panel-label">MONITORED NETWORK</span><span className="count-tag">04</span></div>
    <div className="junction-list">{urbanGridTopology.junctions.map((junction) => {
      const data = trafficByIntersection[junction.id]
      const visual = selectIntersectionVisual(data)
      return <button key={junction.id} className={`junction-row status-${visual.status} ${selectedJunctionId === junction.id ? 'selected' : ''}`} onClick={() => onSelectJunction(junction.id)} aria-label={`Focus ${junction.id} ${junction.name}`}><span className="junction-row-id">{junction.id}</span><span><b>{junction.name}</b><small>{data ? `${data.total_queue} queued` : 'Awaiting data'}</small></span><i className="traffic-dot" /></button>
    })}</div>
    <div className="side-health">
      <div className="sidebar-heading"><span className="panel-label">CONTROL LOOP</span><span className="mode-tag">{loopStatus?.mode ?? 'OFFLINE'}</span></div>
      <p>{loopStatus ? loopStatus.is_running ? 'Simulation running' : 'Ready to step' : 'Waiting for backend'}</p>
      <span className="loop-detail">{loopStatus ? 'Advance simulation & apply control policy' : 'Connect SUMO to enable controls'}</span>
      <button className="step-button" aria-label={stepping ? 'Stepping control loop' : 'Step control loop'} title={stepDisabled ? 'Connect SUMO to enable controls' : stepping ? 'Stepping control loop' : 'Step control loop'} aria-busy={stepping} disabled={stepDisabled || stepping} onClick={() => { void step() }}><Icon name="activity" size={16} /><span className="step-label">{stepping ? 'Stepping…' : 'Step control loop'}</span><span className="step-arrow"><Icon name="arrow" size={14} /></span></button>
    </div>
    <div className="sidebar-note"><span className="tiny-grid">▦</span><div>Urban Grid<small>4 nodes · schematic city</small></div></div>
  </aside>
}
