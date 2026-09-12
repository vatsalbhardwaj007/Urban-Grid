import { buildings } from './mockBuildings'
import { junctions, roads, signalDefinitions } from './mockNetwork'
import type { NetworkConfig } from '../types/digitalTwin'

/** Static spatial configuration. A future backend coordinate adapter can replace this source. */
export const mockTopology: NetworkConfig = { junctions, roads, buildings, signalDefinitions }
