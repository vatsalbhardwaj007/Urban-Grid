import { useState } from 'react'
import { TopBar } from './components/layout/TopBar'
import { LeftSidebar } from './components/layout/LeftSidebar'
import { RightSidebar } from './components/layout/RightSidebar'
import { TrafficMap } from './components/traffic-map/TrafficMap'
import { TrafficCharts } from './components/analytics/TrafficCharts'
import { DigitalTwinScene } from './components/DigitalTwin/DigitalTwinScene'
import { urbanGridTopology } from './data/urbanGridTopology'
import { TrafficProvider, useTrafficStore } from './state/trafficStore'
import { selectNetworkOverview } from './selectors/trafficVisuals'
import './App.css'

function UrbanGridDashboard() {
  const [activeNav, setActiveNav] = useState('Live View')
  const [is3DMode, setIs3DMode] = useState(false)
  const [resetSignal, setResetSignal] = useState(0)

  const traffic = useTrafficStore()
  const network = selectNetworkOverview(traffic.trafficByIntersection)

  const handleReset = () => {
    setResetSignal((prev) => prev + 1)
  }

  const handleStep = () => {
    if (traffic.loopStatus?.mode === 'AUTO') {
      void traffic.stepAiLoop()
    } else {
      void traffic.stepSim(1)
    }
  }

  return (
    <main className="ug-app-shell">
      {/* 1. TOP NAVIGATION BAR */}
      <TopBar
        status={traffic.status}
        health={traffic.health}
        lastSimulationTimestamp={traffic.lastSimulationTimestamp}
        activeNav={activeNav}
        onNavChange={(tab) => {
          setActiveNav(tab)
          if (tab === 'Simulation') setIs3DMode(true)
          if (tab === 'Live View') setIs3DMode(false)
        }}
      />

      {/* 2. THREE-COLUMN WORKSPACE */}
      <div className="ug-workspace">
        {/* LEFT SIDEBAR */}
        <LeftSidebar
          health={traffic.health}
          socketStatus={traffic.status}
          loopStatus={traffic.loopStatus}
          selectedJunctionId={traffic.selectedJunctionId}
          trafficByIntersection={traffic.trafficByIntersection}
          isAutoRunning={traffic.isAutoRunning}
          onSelectJunction={traffic.setSelectedJunctionId}
          onSetMode={traffic.setMode}
          onToggleAutoRun={traffic.toggleAutoRun}
          onStep={handleStep}
          onReset={handleReset}
          onInjectCongestion={traffic.injectCongestion}
          onResolveCongestion={traffic.resolveCongestion}
          onAdjustTimer={traffic.adjustSignalTimer}
        />

        {/* CENTER COMMAND SURFACE: 2D TRAFFIC MAP (OR 3D DIGITAL TWIN) */}
        <section className="ug-center-surface" aria-label="Center Traffic Visualization">
          <div className="center-header">
            <div className="center-header-left">
              <span className="live-indicator-dot" />
              <span className="view-title">
                {is3DMode ? '3D DIGITAL TWIN' : '2D INTERACTIVE TRAFFIC MAP'}
              </span>
              <span className="divider">/</span>
              <span className="network-tag">M2 CANONICAL CANONICAL 2×2 GRID</span>
            </div>
            <div className="center-header-right">
              <button
                className="view-toggle-btn"
                onClick={() => setIs3DMode((prev) => !prev)}
                title="Switch between 2D SVG Map and 3D WebGL Digital Twin"
              >
                {is3DMode ? '▧ Switch to 2D Map' : '❖ Switch to 3D Twin'}
              </button>
              <button className="reset-cam-btn" onClick={handleReset} title="Reset viewport">
                ↺ Reset View
              </button>
            </div>
          </div>

          <div className="map-view-wrapper">
            {is3DMode ? (
              <DigitalTwinScene
                network={urbanGridTopology}
                trafficByIntersection={traffic.trafficByIntersection}
                viewMode="city"
                buildingStyle="solid"
                selectedJunctionId={traffic.selectedJunctionId}
                followedVehicleId={null}
                onSelectJunction={traffic.setSelectedJunctionId}
                resetSignal={resetSignal}
              />
            ) : (
              <TrafficMap
                trafficByIntersection={traffic.trafficByIntersection}
                selectedJunctionId={traffic.selectedJunctionId}
                onSelectJunction={traffic.setSelectedJunctionId}
                latestIntervention={traffic.latestIntervention}
                onAdjustTimer={traffic.adjustSignalTimer}
                onInjectCongestion={traffic.injectCongestion}
                onResolveCongestion={traffic.resolveCongestion}
              />
            )}
          </div>

          {/* BOTTOM LIVE ANALYTICS CHARTS */}
          <TrafficCharts
            history={traffic.history}
            currentVehicles={network.totalVehicles}
            currentSpeed={network.meanSpeed}
            currentQueue={network.totalQueue}
            currentDensity={network.meanDensity}
          />
        </section>

        {/* RIGHT SIDEBAR */}
        <RightSidebar
          trafficByIntersection={traffic.trafficByIntersection}
          selectedJunctionId={traffic.selectedJunctionId}
          onSelectJunction={traffic.setSelectedJunctionId}
          loopStatus={traffic.loopStatus}
          latestIntervention={traffic.latestIntervention}
          onApplyAction={traffic.applyCurrentSignal}
          onAdjustTimer={traffic.adjustSignalTimer}
          onResolveCongestion={traffic.resolveCongestion}
        />

      </div>
    </main>
  )
}

function App() {
  return (
    <TrafficProvider>
      <UrbanGridDashboard />
    </TrafficProvider>
  )
}

export default App
