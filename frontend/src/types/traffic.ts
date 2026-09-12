/** Exact M2 TrafficState v1 contract. Do not add frontend-only fields here. */
export type SignalPhase = 'RED' | 'YELLOW' | 'GREEN'
export type ActionSource = 'AI' | 'FALLBACK' | 'MANUAL'

export interface LaneFeature {
  lane_id: string
  vehicle_count: number
  mean_speed: number
  queue_length: number
  occupancy: number
  arrival_rate: number
  density: number
  flow: number
}

export interface TrafficState {
  timestamp: number
  intersection_id: string
  lane_features: LaneFeature[]
  total_queue: number
  mean_speed: number
  arrival_rate: number
  density: number
  signal_phase: SignalPhase
  green_remaining: number
}

export interface TrafficUpdateEvent { event: 'traffic.update'; data: TrafficState }
export interface PongEvent { event: 'pong' }
export type WebSocketIncomingMessage = TrafficUpdateEvent | PongEvent
export type TrafficSnapshot = Record<string, TrafficState>

export interface HealthResponse { status: 'ok'; simulation_connected: boolean; simulation_time: number | null }
export interface ApiErrorResponse { detail: string | Array<{ loc: Array<string | number>; msg: string; type: string }> }
export interface ControlLoopStatus { is_running: boolean; current_cycle: number; step_interval: number; cycle_delay: number; error_policy: string; decision_engine: string }
export interface SignalActuationResult { success: boolean; target: string; applied_duration: number; current_phase: string; applied_to: string; source: ActionSource; message: string }
export interface ControlCycleResult { cycle: number; simulation_time: number; states: TrafficSnapshot; actions_attempted: number; action_results: SignalActuationResult[]; errors: string[]; success: boolean }

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const isSignalPhase = (value: unknown): value is SignalPhase => value === 'RED' || value === 'YELLOW' || value === 'GREEN'

export function isLaneFeature(value: unknown): value is LaneFeature {
  return isRecord(value) && typeof value.lane_id === 'string' && isNumber(value.vehicle_count) && isNumber(value.mean_speed) && isNumber(value.queue_length) && isNumber(value.occupancy) && isNumber(value.arrival_rate) && isNumber(value.density) && isNumber(value.flow)
}

export function isTrafficState(value: unknown): value is TrafficState {
  return isRecord(value) && isNumber(value.timestamp) && typeof value.intersection_id === 'string' && Array.isArray(value.lane_features) && value.lane_features.every(isLaneFeature) && isNumber(value.total_queue) && isNumber(value.mean_speed) && isNumber(value.arrival_rate) && isNumber(value.density) && isSignalPhase(value.signal_phase) && isNumber(value.green_remaining)
}

export function isTrafficSnapshot(value: unknown): value is TrafficSnapshot {
  return isRecord(value) && Object.values(value).every(isTrafficState)
}

export function parseWebSocketMessage(value: unknown): WebSocketIncomingMessage | null {
  if (!isRecord(value) || typeof value.event !== 'string') return null
  if (value.event === 'pong') return { event: 'pong' }
  return value.event === 'traffic.update' && isTrafficState(value.data) ? { event: 'traffic.update', data: value.data } : null
}
