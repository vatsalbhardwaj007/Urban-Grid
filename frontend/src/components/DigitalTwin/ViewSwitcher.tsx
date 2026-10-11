import { viewModes } from '../../data/viewModes'
import type { ViewMode } from '../../types/digitalTwin'
import { Icon } from '../Icon'

export function ViewSwitcher({ viewMode, onModeChange, followVehicleAvailable }: { viewMode: ViewMode; onModeChange: (view: ViewMode) => void; followVehicleAvailable: boolean }) {
  return <nav className="view-switcher" aria-label="Camera views">{viewModes.map((view) =>
    <button key={view.id} className={`view-tab ${viewMode === view.id ? 'active' : ''}`} aria-pressed={viewMode === view.id} disabled={view.id === 'followVehicle' && !followVehicleAvailable} title={view.id === 'followVehicle' && !followVehicleAvailable ? 'Select a real SUMO vehicle in the scene first' : view.description} onClick={() => onModeChange(view.id)}>
      <Icon name={view.id} /><span>{view.label}</span>{view.id === 'followVehicle' && !followVehicleAvailable && <small>SELECT VEHICLE</small>}
    </button>,
  )}</nav>
}
