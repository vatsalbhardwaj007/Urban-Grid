/** Exact M2 TrafficState v1 contract. Do not add frontend-only fields here. */
export type SignalPhase = 'RED' | 'YELLOW' | 'GREEN'
export type ActionSource = 'AI' | 'FALLBACK' | 'MANUAL'
export type ControlMode = 'AUTO' | 'MANUAL' | 'EMERGENCY'

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
/** A real SUMO vehicle, emitted separately from aggregate TrafficState v1. */
export interface VehicleState {
  id: string
  x: number
  y: number
  speed: number
  angle: number
  lane_id: string
  road_id: string | null
  vehicle_type: string | null
}
export interface VehicleSnapshot { timestamp: number; vehicles: VehicleState[] }
/**
 * Rendering track retained by the runtime store.  `previous` is the last real
 * observation for the same stable SUMO ID; the renderer only interpolates
 * between these two observations and never extrapolates a fabricated route.
 */
export interface VehicleTrack {
  vehicle: VehicleState
  previous: VehicleState
  previousSnapshotTimestamp: number
  snapshotTimestamp: number
  receivedAt: number
}
export interface VehicleSnapshotEvent { event: 'vehicle.snapshot'; data: VehicleSnapshot }
export interface PongEvent { event: 'pong' }
export type WebSocketIncomingMessage = TrafficUpdateEvent | VehicleSnapshotEvent | PongEvent
export type TrafficSnapshot = Record<string, TrafficState>

export interface HealthResponse { status: 'ok'; simulation_connected: boolean; simulation_time: number | null }
export interface ApiErrorResponse { detail: string | Array<{ loc: Array<string | number>; msg: string; type: string }> }
export interface ControlLoopStatus { mode: ControlMode; is_running: boolean; current_cycle: number; step_interval: number; cycle_delay: number; error_policy: string; decision_engine: string }
/** Returned by the existing control-mode endpoint; it intentionally contains no telemetry. */
export interface SignalActuationResult { success: boolean; target: string; applied_duration: number; current_phase: string; applied_to: string; source: ActionSource; message: string }
/** M2 declares control-loop action_results as list[dict[str, Any]]. */
export interface ControlCycleResult { cycle: number; simulation_time: number; mode: ControlMode; states: TrafficSnapshot; actions_attempted: number; action_results: Array<Record<string, unknown>>; errors: string[]; success: boolean }

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const isNonNegativeNumber = (value: unknown): value is number => isNumber(value) && value >= 0
const isNonNegativeInteger = (value: unknown): value is number => isNumber(value) && Number.isInteger(value) && value >= 0
const isSignalPhase = (value: unknown): value is SignalPhase => value === 'RED' || value === 'YELLOW' || value === 'GREEN'
const isActionSource = (value: unknown): value is ActionSource => value === 'AI' || value === 'FALLBACK' || value === 'MANUAL'
export const isControlMode = (value: unknown): value is ControlMode => value === 'AUTO' || value === 'MANUAL' || value === 'EMERGENCY'

export function isLaneFeature(value: unknown): value is LaneFeature {
  return isRecord(value) && typeof value.lane_id === 'string' && isNonNegativeInteger(value.vehicle_count) && isNonNegativeNumber(value.mean_speed) && isNonNegativeInteger(value.queue_length) && isNonNegativeNumber(value.occupancy) && isNonNegativeNumber(value.arrival_rate) && isNonNegativeNumber(value.density) && isNonNegativeNumber(value.flow)
}

export function isTrafficState(value: unknown): value is TrafficState {
  return isRecord(value) && isNonNegativeNumber(value.timestamp) && typeof value.intersection_id === 'string' && Array.isArray(value.lane_features) && value.lane_features.every(isLaneFeature) && isNonNegativeInteger(value.total_queue) && isNonNegativeNumber(value.mean_speed) && isNonNegativeNumber(value.arrival_rate) && isNonNegativeNumber(value.density) && isSignalPhase(value.signal_phase) && isNonNegativeNumber(value.green_remaining)
}

export function isVehicleState(value: unknown): value is VehicleState {
  return isRecord(value) && typeof value.id === 'string' && value.id.length > 0 && isNumber(value.x) && isNumber(value.y) && isNonNegativeNumber(value.speed) && isNumber(value.angle) && typeof value.lane_id === 'string' && (value.road_id === null || typeof value.road_id === 'string') && (value.vehicle_type === null || typeof value.vehicle_type === 'string')
}

export function isVehicleSnapshot(value: unknown): value is VehicleSnapshot {
  return isRecord(value) && isNonNegativeNumber(value.timestamp) && Array.isArray(value.vehicles) && value.vehicles.every(isVehicleState) && new Set(value.vehicles.map((vehicle) => vehicle.id)).size === value.vehicles.length
}

export function isTrafficSnapshot(value: unknown): value is TrafficSnapshot {
  return isRecord(value) && Object.values(value).every(isTrafficState)
}

export function parseWebSocketMessage(value: unknown): WebSocketIncomingMessage | null {
  if (!isRecord(value) || typeof value.event !== 'string') return null
  if (value.event === 'pong') return { event: 'pong' }
  if (value.event === 'traffic.update' && isTrafficState(value.data)) return { event: 'traffic.update', data: value.data }
  if (value.event === 'vehicle.snapshot' && isVehicleSnapshot(value.data)) return { event: 'vehicle.snapshot', data: value.data }
  return null
}

/** Safe presentation selector for the generic M2 control-loop result objects. */
export function isSignalActuationResult(value: unknown): value is SignalActuationResult {
  return isRecord(value) && typeof value.success === 'boolean' && typeof value.target === 'string' && isNumber(value.applied_duration) && typeof value.current_phase === 'string' && typeof value.applied_to === 'string' && isActionSource(value.source) && typeof value.message === 'string'
}
