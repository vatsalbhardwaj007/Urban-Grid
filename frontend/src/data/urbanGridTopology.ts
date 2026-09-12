import { buildings } from './mockBuildings'
import type { NetworkConfig } from '../types/digitalTwin'

/** Static render-only topology for M2's canonical I1–I4 2×2 grid. */
export const CANONICAL_INTERSECTION_IDS = ['I1', 'I2', 'I3', 'I4'] as const

export const urbanGridTopology: NetworkConfig = {
  junctions: [
    { id: 'I1', name: 'Northwest', x: -11, z: 9, type: 'four-way' },
    { id: 'I2', name: 'Northeast', x: 11, z: 9, type: 'four-way' },
    { id: 'I3', name: 'Southwest', x: -11, z: -9, type: 'four-way' },
    { id: 'I4', name: 'Southeast', x: 11, z: -9, type: 'four-way' },
  ],
  roads: [
    { id: 'I1-I2', from: 'I1', to: 'I2', lanes: 2 }, { id: 'I1-I3', from: 'I1', to: 'I3', lanes: 2 },
    { id: 'I2-I4', from: 'I2', to: 'I4', lanes: 2 }, { id: 'I3-I4', from: 'I3', to: 'I4', lanes: 2 },
  ],
  buildings,
  signalDefinitions: [
    { id: 'signal-I1', junctionId: 'I1', offset: [1.6, 1.6], orientation: 0 }, { id: 'signal-I2', junctionId: 'I2', offset: [-1.6, 1.6], orientation: Math.PI },
    { id: 'signal-I3', junctionId: 'I3', offset: [1.6, -1.6], orientation: 0 }, { id: 'signal-I4', junctionId: 'I4', offset: [-1.6, -1.6], orientation: Math.PI },
  ],
}
