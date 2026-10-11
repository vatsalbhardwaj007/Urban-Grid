import { useState } from 'react'
import { viewModes } from '../../data/viewModes'
import { urbanGridTopology } from '../../data/urbanGridTopology'
import { selectIntersectionVisual } from '../../selectors/trafficVisuals'
import type { ControlLoopStatus, ControlMode, TrafficSnapshot } from '../../types/traffic'
import type { ViewMode } from '../../types/digitalTwin'
import { Icon } from '../Icon'

type Props = { viewMode: ViewMode; selectedJunctionId: string; onModeChange: (mode: ViewMode) => void; onSelectJunction: (id: string) => void; onStepAiLoop: () => Promise<void>; onSetControlMode: (mode: ControlMode) => Promise<void>; stepDisabled: boolean; loopStatus: ControlLoopStatus | null; trafficByIntersection: TrafficSnapshot; followVehicleAvailable: boolean }

export function ControlSidebar({ viewMode, selectedJunctionId, onModeChange, onSelectJunction, onStepAiLoop, onSetControlMode, stepDisabled, loopStatus, trafficByIntersection, followVehicleAvailable }: Props) {
  const [stepping, setStepping] = useState(false)
  const [changingMode, setChangingMode] = useState<ControlMode | null>(null)
  const step = async () => { setStepping(true); try { await onStepAiLoop() } finally { setStepping(false) } }
  const setMode = async (mode: ControlMode) => { setChangingMode(mode); try { await onSetControlMode(mode) } finally { setChangingMode(null) } }
  return <aside className="control-sidebar" aria-label="Monitoring controls">
    <div className="sidebar-heading"><span className="panel-label">WORKSPACE</span><span className="workspace-number">01</span></div>
    <div className="mode-list">{viewModes.map((mode) => { const disabled = mode.id === 'followVehicle' && !followVehicleAvailable; return <button key={mode.id} className={`mode-button ${viewMode === mode.id ? 'active' : ''}`} aria-pressed={viewMode === mode.id} disabled={disabled} title={disabled ? 'Select a real SUMO vehicle in the scene first' : mode.description} onClick={() => onModeChange(mode.id)}><Icon name={mode.id} /><span>{mode.label}</span>{disabled && <span className="unavailable-mark">—</span>}</button> })}</div>
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
      <div className="control-mode-picker" role="group" aria-label="Live control mode">
        {(['AUTO', 'MANUAL', 'EMERGENCY'] as const).map((mode) => <button key={mode} className={loopStatus?.mode === mode ? 'active' : ''} aria-pressed={loopStatus?.mode === mode} disabled={stepDisabled || changingMode !== null} title={stepDisabled ? 'Connect SUMO to change the control mode' : `${mode}: ${mode === 'AUTO' ? 'existing AI decisions may actuate' : mode === 'MANUAL' ? 'AI decisions are observed but not actuated' : 'existing emergency fallback policy'}`} onClick={() => { void setMode(mode) }}>{changingMode === mode ? '…' : mode}</button>)}
      </div>
      <button className="step-button" aria-label={stepping ? 'Stepping control loop' : 'Step control loop'} title={stepDisabled ? 'Connect SUMO to enable controls' : stepping ? 'Stepping control loop' : 'Step control loop'} aria-busy={stepping} disabled={stepDisabled || stepping} onClick={() => { void step() }}><Icon name="activity" size={16} /><span className="step-label">{stepping ? 'Stepping…' : 'Step control loop'}</span><span className="step-arrow"><Icon name="arrow" size={14} /></span></button>
      <span className="control-truth">Runs one server-side cycle. Scenario playback and prediction horizon are not exposed by this API.</span>
    </div>
    <div className="sidebar-note"><span className="tiny-grid">▦</span><div>Urban Grid<small>4 nodes · schematic city</small></div></div>
  </aside>
}
