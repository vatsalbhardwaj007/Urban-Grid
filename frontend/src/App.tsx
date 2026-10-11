import { useCallback, useEffect, useState } from 'react'
import { DigitalTwinScene } from './components/DigitalTwin/DigitalTwinScene'
import { ViewSwitcher } from './components/DigitalTwin/ViewSwitcher'
import { ContextPanel } from './components/layout/ContextPanel'
import { ControlSidebar } from './components/layout/ControlSidebar'
import { TopBar } from './components/layout/TopBar'
import { Icon } from './components/Icon'
import { TrafficAnalyticsDashboard } from './components/analytics/TrafficAnalyticsDashboard'
import { DisplayErrorBoundary } from './components/ErrorBoundary'
import { dashboardHash, dashboardScreenFromHash, type DashboardScreen } from './data/dashboardNavigation'
import type { AnalyticsScope } from './selectors/trafficAnalytics'
import { urbanGridTopology } from './data/urbanGridTopology'
import { viewModes } from './data/viewModes'
import { TrafficProvider, useTrafficStore } from './state/trafficStore'
import type { BuildingStyle, ViewMode } from './types/digitalTwin'
import type { TrafficSnapshot } from './types/traffic'
import './App.css'

function UrbanGridDashboard() {
  const [screen, setScreen] = useState<DashboardScreen>(() => dashboardScreenFromHash(window.location.hash))
  const [viewMode, setViewMode] = useState<ViewMode>('city')
  const [selectedJunctionId, setSelectedJunctionId] = useState('I1')
  const [analyticsScope, setAnalyticsScope] = useState<AnalyticsScope>('NETWORK')
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null)
  const [buildingStyle, setBuildingStyle] = useState<BuildingStyle>('solid')
  const [showBuildings, setShowBuildings] = useState(true)
  const [panMode, setPanMode] = useState(false)
  const [resetSignal, setResetSignal] = useState(0)
  const [focusSignal, setFocusSignal] = useState(0)
  const [zoomRequest, setZoomRequest] = useState<{direction: 1 | -1; sequence: number}>({direction: 1, sequence: 0})
  const traffic = useTrafficStore()
  const selectedJunction = urbanGridTopology.junctions.find((junction) => junction.id === selectedJunctionId) ?? urbanGridTopology.junctions[0]
  // Stale values remain visibly stale in the status indicators; they are never replaced with invented traffic.
  const renderTraffic: TrafficSnapshot = traffic.trafficByIntersection
  const vehicleTracks = Object.values(traffic.vehiclesById)
  const selectedVehicle = selectedVehicleId ? traffic.vehiclesById[selectedVehicleId]?.vehicle : undefined
  const effectiveViewMode = viewMode === 'followVehicle' && !selectedVehicle ? 'city' : viewMode
  const observedCount = Object.keys(renderTraffic).length
  const totalQueue = Object.values(renderTraffic).reduce((sum, state) => sum + state.total_queue, 0)
  const resetCamera = useCallback(() => { setViewMode('city'); setResetSignal((value) => value + 1) }, [])
  const selectJunction = useCallback((id: string) => { setSelectedVehicleId(null); setSelectedJunctionId(id); setAnalyticsScope(id as AnalyticsScope); setViewMode('junction'); setFocusSignal((value) => value + 1) }, [])
  const navigate = useCallback((next: DashboardScreen) => { if (next === screen) return; window.history.pushState({ screen: next }, '', dashboardHash(next) || `${window.location.pathname}${window.location.search}`); setScreen(next) }, [screen])
  const selectVehicle = useCallback((id: string) => { setSelectedVehicleId(id) }, [])
  const followSelectedVehicle = useCallback(() => {
    if (!selectedVehicleId || !traffic.vehiclesById[selectedVehicleId]) return
    setViewMode('followVehicle')
    setFocusSignal((value) => value + 1)
  }, [selectedVehicleId, traffic.vehiclesById])
  const changeMode = useCallback((mode: ViewMode) => {
    if (mode === 'followVehicle' && !selectedVehicleId) return
    if (mode === 'city') { resetCamera(); return }
    setViewMode(mode)
    setFocusSignal((value) => value + 1)
  }, [resetCamera, selectedVehicleId])
  const zoom = (direction: 1 | -1) => setZoomRequest((previous) => ({direction, sequence: previous.sequence + 1}))
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && (event.target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(event.target.tagName))) return
      if (event.ctrlKey || event.metaKey || event.altKey) return
      if (event.key.toLowerCase() === 'r') resetCamera()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [resetCamera])
  useEffect(() => { const syncScreen = () => setScreen(dashboardScreenFromHash(window.location.hash)); window.addEventListener('popstate', syncScreen); return () => window.removeEventListener('popstate', syncScreen) }, [])

  return <main className="app-shell">
    <TopBar status={traffic.status} health={traffic.health} lastReceivedAt={traffic.lastReceivedAt} screen={screen} onNavigate={navigate} />
    <div className="live-dashboard" hidden={screen !== 'live'}><div className="workspace">
      <ControlSidebar viewMode={effectiveViewMode} selectedJunctionId={selectedJunctionId} onModeChange={changeMode} onSelectJunction={selectJunction} onStepAiLoop={traffic.stepAiLoop} onSetControlMode={traffic.setControlMode} stepDisabled={traffic.health?.simulation_connected !== true} loopStatus={traffic.loopStatus} trafficByIntersection={renderTraffic} followVehicleAvailable={Boolean(selectedVehicle)} />
      <section className="twin-area" aria-label="Urban traffic digital twin">
        <header className="twin-header"><div><div className="eyebrow">DIGITAL TWIN <span>/</span> URBAN DISTRICT</div><h2>City traffic monitor</h2></div><span className="scene-mode">3D <span>{traffic.status === 'connected' ? 'LIVE VIEW' : traffic.status === 'rest-fallback' ? 'REST VIEW' : 'LAST REAL SNAPSHOT'}</span></span></header>
        <div className="network-summary"><span><i className="summary-dot" /><b>{observedCount}</b> / 4 {traffic.status === 'connected' ? 'nodes reporting' : 'nodes received'}</span><span><b>{observedCount ? totalQueue : '—'}</b> queued vehicles</span><span><b>{vehicleTracks.length}</b> {traffic.status === 'connected' ? 'live vehicles' : 'last observed vehicles'}</span><span className="summary-mode">{traffic.controlMode ?? traffic.loopStatus?.mode ?? 'AWAITING BACKEND'}</span></div>
        <div className="scene-wrap">
          <DisplayErrorBoundary scope="3D digital twin" className="display-boundary-fill"><DigitalTwinScene network={urbanGridTopology} trafficByIntersection={renderTraffic} vehicleTracks={vehicleTracks} viewMode={effectiveViewMode} buildingStyle={buildingStyle} showBuildings={showBuildings} panMode={panMode} selectedJunctionId={selectedJunctionId} selectedVehicleId={selectedVehicleId} followedVehicleId={effectiveViewMode === 'followVehicle' ? selectedVehicleId : null} onSelectJunction={selectJunction} onSelectVehicle={selectVehicle} resetSignal={resetSignal} focusSignal={focusSignal} zoomRequest={zoomRequest} /></DisplayErrorBoundary>
          <div className="scene-caption"><span className="panel-label">{viewModes.find((view) => view.id === effectiveViewMode)?.label.toUpperCase()}</span><span>Schematic city · real SUMO vehicles</span></div>
          {effectiveViewMode === 'building' && <div className="style-toggle" aria-label="Building render style"><button aria-pressed={buildingStyle === 'solid'} className={buildingStyle === 'solid' ? 'active' : ''} onClick={() => setBuildingStyle('solid')}>Solid</button><button aria-pressed={buildingStyle === 'wireframe'} className={buildingStyle === 'wireframe' ? 'active' : ''} onClick={() => setBuildingStyle('wireframe')}>Wireframe</button></div>}
          <div className="camera-toolbar" role="group" aria-label="Camera controls"><button aria-label="Zoom in" title="Zoom in · mouse wheel up" onClick={() => zoom(1)}><Icon name="plus" /></button><button aria-label="Zoom out" title="Zoom out · mouse wheel down" onClick={() => zoom(-1)}><Icon name="minus" /></button><div className="toolbar-divider"/><button aria-label="Pan camera" aria-pressed={panMode} title={panMode ? 'Pan enabled · click to return to orbit' : 'Pan with left-drag · right-drag always pans'} onClick={() => setPanMode((value) => !value)}><Icon name="localTwin" /></button><button aria-label="Reset camera" title="Reset camera to City View · R" onClick={resetCamera}><Icon name="reset" /></button><button aria-label="Show buildings" aria-pressed={showBuildings} title="Toggle static building layer" onClick={() => setShowBuildings((value) => !value)}><Icon name="layers" /></button></div>
          <div className="scene-legend" aria-label="Traffic legend"><span className="legend-heading">CONGESTION</span><span><i className="flowing"/>Low</span><span><i className="moderate"/>Moderate</span><span><i className="critical"/>High</span><span><i className="unknown"/>No data</span></div>
          <div className="scene-instructions">Drag to {panMode ? 'pan' : 'orbit'} <span>·</span> Right-drag to pan <span>·</span> Scroll to zoom</div>
        </div>
        <ViewSwitcher viewMode={effectiveViewMode} onModeChange={changeMode} followVehicleAvailable={Boolean(selectedVehicle)} />
        <footer className="telemetry-footer"><span className={`feed-state connection-${traffic.status}`}><i/>{traffic.status.replace('-', ' ').toUpperCase()}</span><span className="footer-message" title={traffic.error ?? undefined}>{traffic.error ?? (traffic.malformedEvents ? `${traffic.malformedEvents} invalid events ignored` : 'SUMO → TRAFFIC STATE → DIGITAL TWIN')}</span><span className="reset-shortcut"><kbd>R</kbd> Reset view</span></footer>
      </section>
      <DisplayErrorBoundary scope="Intersection intelligence panel"><ContextPanel junction={selectedJunction} traffic={renderTraffic[selectedJunction.id]} allTraffic={renderTraffic} availableJunctions={urbanGridTopology.junctions} loopStatus={traffic.loopStatus} controlMode={traffic.controlMode} health={traffic.health} intersectionAvailable={traffic.intersectionIds.includes(selectedJunction.id)} actionHistory={traffic.actionHistory} latestIntervention={traffic.latestIntervention} lastControlCycle={traffic.lastControlCycle} status={traffic.status} onSelectJunction={selectJunction} onApplyManualSignal={traffic.applyManualSignalTiming} selectedVehicle={selectedVehicle} onFollowVehicle={followSelectedVehicle} onClearVehicle={() => { setSelectedVehicleId(null); if (effectiveViewMode === 'followVehicle') resetCamera() }} /></DisplayErrorBoundary>
    </div></div>
    <div className="analytics-screen" hidden={screen !== 'analytics'}><DisplayErrorBoundary scope="Traffic analytics dashboard"><TrafficAnalyticsDashboard trafficByIntersection={renderTraffic} history={traffic.analyticsHistory} status={traffic.status} scope={analyticsScope} onScopeChange={(scope) => { setAnalyticsScope(scope); if (scope !== 'NETWORK') selectJunction(scope) }} /></DisplayErrorBoundary></div>
  </main>
}

function App() { return <TrafficProvider><DisplayErrorBoundary scope="Operations dashboard"><UrbanGridDashboard /></DisplayErrorBoundary></TrafficProvider> }
export default App
