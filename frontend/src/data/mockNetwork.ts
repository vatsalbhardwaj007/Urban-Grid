import type { Junction, Road, SignalDefinition } from '../types/digitalTwin'

export const junctions: Junction[] = [
  { id: 'J1', name: 'West Gate',        x: -12, z:  7,  type: 'three-way' },
  { id: 'J2', name: 'North Loop',       x:  -3, z:  5,  type: 'four-way' },
  { id: 'J3', name: 'East Market',      x:   8, z:  8,  type: 'three-way' },
  { id: 'J4', name: 'Central Exchange', x:   4, z: -2,  type: 'four-way' },
  { id: 'J5', name: 'Harbor Gate',      x:  -8, z: -7,  type: 'four-way' },
]

export const roads: Road[] = [
  { id: 'R1', from: 'J1', to: 'J2', lanes: 2 },
  { id: 'R2', from: 'J2', to: 'J3', lanes: 2 },
  { id: 'R3', from: 'J3', to: 'J4', lanes: 2 },
  { id: 'R4', from: 'J4', to: 'J5', lanes: 3 },
  { id: 'R5', from: 'J5', to: 'J1', lanes: 2 },
  { id: 'R6', from: 'J2', to: 'J4', lanes: 2 },
  { id: 'R7', from: 'J2', to: 'J5', lanes: 2 },
]

export const signalDefinitions: SignalDefinition[] = [
  { id: 'S1', junctionId: 'J4', offset: [ 1.6,  1.6], orientation: 0 },
  { id: 'S2', junctionId: 'J4', offset: [-1.6, -1.6], orientation: Math.PI },
  { id: 'S3', junctionId: 'J2', offset: [ 1.4, -1.4], orientation: 0 },
  { id: 'S4', junctionId: 'J2', offset: [-1.4,  1.4], orientation: Math.PI },
  { id: 'S5', junctionId: 'J5', offset: [ 1.4,  1.4], orientation: Math.PI / 2 },
  { id: 'S6', junctionId: 'J3', offset: [-1.4,  1.4], orientation: -Math.PI / 2 },
  { id: 'S7', junctionId: 'J1', offset: [ 1.2, -1.2], orientation: 0 },
]
