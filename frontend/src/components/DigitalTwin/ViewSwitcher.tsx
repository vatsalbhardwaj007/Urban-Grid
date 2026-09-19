import { viewModes } from '../../data/viewModes'
import type { ViewMode } from '../../types/digitalTwin'
import { Icon } from '../Icon'

export function ViewSwitcher({ viewMode, onModeChange }: { viewMode: ViewMode; onModeChange: (view: ViewMode) => void }) {
  return <nav className="view-switcher" aria-label="Camera views">{viewModes.map((view) =>
    <button key={view.id} className={`view-tab ${viewMode === view.id ? 'active' : ''}`} aria-pressed={viewMode === view.id} disabled={view.disabled} title={view.description} onClick={() => onModeChange(view.id)}>
      <Icon name={view.id} /><span>{view.label}</span>{view.disabled && <small>UNAVAILABLE</small>}
    </button>,
  )}</nav>
}
