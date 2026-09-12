export type ViewMode = 'city' | 'junction' | 'building' | 'followVehicle' | 'localTwin'
export type BuildingStyle = 'solid' | 'wireframe'
export type TrafficStatus = 'flowing' | 'moderate' | 'critical'
export type TrafficVisualStatus = TrafficStatus | 'unknown'
export type Junction = { id: string; name: string; x: number; z: number; type: 'four-way' | 'three-way' }
export type Road = { id: string; from: string; to: string; lanes: number }
export type Building = { id: string; x: number; z: number; width: number; depth: number; height: number; variant: 'tower' | 'midrise' | 'commercial' | 'corner' }
/** Backend-compatible dynamic vehicle state. Visual treatment stays in the frontend. */
export type VehicleState = { id: string; x: number; z: number; heading: number; speed: number }
export type SignalDefinition = { id: string; junctionId: string; offset: [number, number]; orientation?: number }
export type NetworkConfig = {
  junctions: Junction[]
  roads: Road[]
  buildings: Building[]
  signalDefinitions: SignalDefinition[]
}
