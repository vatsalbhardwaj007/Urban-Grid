import type { TrafficRuntimeState } from '../types/digitalTwin'
import { mockVehicles } from './mockVehicles'

/** Temporary central source for runtime data; later replaced by WebSocket updates. */
export const initialTrafficState: TrafficRuntimeState = {
  vehicles: mockVehicles,
  signalStates: { S1: 'red', S2: 'green', S3: 'green', S4: 'red', S5: 'yellow', S6: 'green', S7: 'red' },
  roadStatuses: { R1: 'flowing', R2: 'flowing', R3: 'moderate', R4: 'critical', R5: 'moderate', R6: 'flowing', R7: 'flowing' },
  junctionStates: {
    J1: { congestion: 24, status: 'flowing' }, J2: { congestion: 18, status: 'flowing' },
    J3: { congestion: 31, status: 'moderate' }, J4: { congestion: 42, status: 'critical' },
    J5: { congestion: 26, status: 'moderate' },
  },
}
