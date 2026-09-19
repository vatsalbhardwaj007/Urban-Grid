import { Html } from '@react-three/drei'
import { memo } from 'react'
import type { Junction, TrafficVisualStatus } from '../../types/digitalTwin'
import type { SignalPhase } from '../../types/traffic'

const labels: Record<TrafficVisualStatus, string> = { flowing: 'FLOWING', moderate: 'MODERATE', critical: 'CRITICAL', unknown: 'NO DATA' }

/** Four DOM labels stay legible at every camera distance and are keyboard accessible. */
export const IntersectionLabel = memo(function IntersectionLabel({ junction, status, phase, selected, onSelect }: { junction: Junction; status: TrafficVisualStatus; phase?: SignalPhase; selected: boolean; onSelect: (id: string) => void }) {
  return <Html position={[junction.x, 3.1, junction.z]} center zIndexRange={[30, 10]}>
    <button className={`junction-label status-${status}${selected ? ' selected' : ''}`} onClick={(event) => { event.stopPropagation(); onSelect(junction.id) }} aria-label={`Focus ${junction.id}, ${junction.name}, ${labels[status].toLowerCase()}, signal ${phase ?? 'unavailable'}`} aria-pressed={selected}>
      <span className="junction-label-id">{junction.id}</span>
      <span className="junction-label-name">{junction.name}</span>
      <span className="junction-label-status"><i />{labels[status]}</span>
      <span className="junction-label-signal" title={`Signal: ${phase ?? 'unavailable'}`} aria-hidden="true">
        {(['RED', 'YELLOW', 'GREEN'] as const).map((color) => <i key={color} className={phase === color ? `active ${color.toLowerCase()}` : ''} />)}
      </span>
    </button>
  </Html>
})
