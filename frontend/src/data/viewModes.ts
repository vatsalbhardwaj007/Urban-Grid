import type { ViewMode } from '../types/digitalTwin'

export const viewModes: Array<{ id: ViewMode; label: string; description: string; disabled?: boolean }> = [
  { id: 'city', label: 'City View', description: 'All four monitored intersections' },
  { id: 'junction', label: 'Junction View', description: 'Focus the selected intersection' },
  { id: 'building', label: 'Building View', description: 'Explore the static city context' },
  { id: 'localTwin', label: 'Local Twin', description: 'Inspect the local road network' },
  { id: 'followVehicle', label: 'Follow Vehicle', description: 'Unavailable: the live feed has no individual vehicle positions', disabled: true },
]
