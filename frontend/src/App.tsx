import { useState } from 'react'
import { DigitalTwinScene } from './components/DigitalTwin/DigitalTwinScene'
import { ViewSwitcher } from './components/DigitalTwin/ViewSwitcher'
import { ContextPanel } from './components/layout/ContextPanel'
import { ControlSidebar } from './components/layout/ControlSidebar'
import { TopBar } from './components/layout/TopBar'
import { urbanGridTopology } from './data/urbanGridTopology'
import { TrafficProvider, useTrafficStore } from './state/trafficStore'
import type { BuildingStyle, ViewMode } from './types/digitalTwin'
import './App.css'

function UrbanGridDashboard() {
  const [viewMode, setViewMode] = useState<ViewMode>('city')
  const [selectedJunctionId, setSelectedJunctionId] = useState('I1')
  const [buildingStyle, setBuildingStyle] = useState<BuildingStyle>('solid')
  const [resetSignal, setResetSignal] = useState(0)
  const traffic = useTrafficStore()
  const selectedJunction = urbanGridTopology.junctions.find((junction) => junction.id === selectedJunctionId) ?? urbanGridTopology.junctions[0]
  const renderTraffic = traffic.status === 'disconnected' && traffic.health?.simulation_connected !== true ? {} : traffic.trafficByIntersection

  return <main className="app-shell">
    <TopBar status={traffic.status} health={traffic.health} lastReceivedAt={traffic.lastReceivedAt} />
    <div className="workspace">
      <ControlSidebar viewMode={viewMode} selectedJunctionId={selectedJunctionId} onModeChange={setViewMode} onSelectJunction={setSelectedJunctionId} onStepAiLoop={traffic.stepAiLoop} stepDisabled={traffic.health?.simulation_connected !== true} loopStatus={traffic.loopStatus} />
      <section className="twin-area" aria-label="Urban traffic digital twin">
        <header className="twin-header"><div className="eyebrow"><span className="live-dot" /> {traffic.status === 'connected' ? 'LIVE DIGITAL TWIN' : 'TRAFFIC TWIN'} <span>/</span> URBAN GRID <span>/</span> M2 STREAM</div><div className="updated">{traffic.lastReceivedAt ? `Updated ${new Date(traffic.lastReceivedAt).toLocaleTimeString()}` : 'Awaiting backend data'} <button onClick={() => setResetSignal((signal) => signal + 1)} title="Reset camera">⌗</button></div></header>
        <div className="scene-wrap">
          {viewMode === 'building' && <div className="style-toggle" aria-label="Building render style"><button className={buildingStyle === 'solid' ? 'active' : ''} onClick={() => setBuildingStyle('solid')}>Solid</button><button className={buildingStyle === 'wireframe' ? 'active' : ''} onClick={() => setBuildingStyle('wireframe')}>Wireframe</button></div>}
          <DigitalTwinScene network={urbanGridTopology} trafficByIntersection={renderTraffic} viewMode={viewMode} buildingStyle={buildingStyle} selectedJunctionId={selectedJunctionId} followedVehicleId={null} onSelectJunction={setSelectedJunctionId} resetSignal={resetSignal} />
          <div className="scene-compass"><b>N</b><span>▲</span><small>0°</small></div><div className="scene-readout"><span>{traffic.status.toUpperCase()}</span><span>{traffic.malformedEvents ? `⚠ ${traffic.malformedEvents} invalid event${traffic.malformedEvents === 1 ? '' : 's'}` : '◉ M2 telemetry'}</span></div><button className="camera-reset" onClick={() => setResetSignal((signal) => signal + 1)}>↻ Reset camera</button><div className="scene-legend"><span><i className="flowing" /> Flowing</span><span><i className="moderate" /> Moderate</span><span><i className="critical" /> Critical</span></div>
        </div>
        <ViewSwitcher viewMode={viewMode} onModeChange={setViewMode} />
        <footer className="hotkeys"><span><kbd>SPACE</kbd> simulation controls</span><span><kbd>R</kbd> reset camera</span><span><kbd>?</kbd> shortcuts</span><span>{traffic.error ?? 'Canonical M2 traffic telemetry'}</span></footer>
      </section>
      <ContextPanel junction={selectedJunction} traffic={renderTraffic[selectedJunction.id]} allTraffic={renderTraffic} availableJunctions={urbanGridTopology.junctions} loopStatus={traffic.loopStatus} latestIntervention={traffic.latestIntervention} />
    </div>
  </main>
}

function App() { return <TrafficProvider><UrbanGridDashboard /></TrafficProvider> }
export default App
