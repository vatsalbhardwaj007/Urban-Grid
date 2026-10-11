import { backendConfig } from '../config/backend'
import type { ControlCycleResult, ControlLoopStatus, ControlMode, ControlModeResponse, HealthResponse, ManualSignalAction, SignalActuationResult, TrafficSnapshot, VehicleSnapshot } from '../types/traffic'
import { isControlMode, isControlModeResponse, isSignalActuationResult, isSimulationTimestamp, isTrafficSnapshot, isVehicleSnapshot } from '../types/traffic'

export class BackendRequestError extends Error {
  readonly status: number | undefined
  constructor(message: string, status?: number) { super(message); this.name = 'BackendRequestError'; this.status = status }
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

function errorDetail(value: unknown) {
  if (!isRecord(value) || !('detail' in value)) return 'Backend request failed.'
  const detail = value.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.filter(isRecord).map((item) => typeof item.msg === 'string' ? item.msg : 'Validation error').join('; ')
  return 'Backend request failed.'
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  let response: Response
  try { response = await fetch(`${backendConfig.httpUrl}${path}`, { headers: { Accept: 'application/json', ...init?.headers }, ...init }) }
  catch (error) { throw new BackendRequestError(error instanceof DOMException && error.name === 'AbortError' ? 'Signal timing request timed out.' : 'Backend is unavailable.') }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new BackendRequestError(errorDetail(body), response.status)
  return body
}

const isHealthResponse = (value: unknown): value is HealthResponse => isRecord(value) && value.status === 'ok' && typeof value.simulation_connected === 'boolean' && (value.simulation_time === null || isSimulationTimestamp(value.simulation_time))
const isControlLoopStatus = (value: unknown): value is ControlLoopStatus => isRecord(value) && isControlMode(value.mode) && typeof value.is_running === 'boolean' && isNumber(value.current_cycle) && isNumber(value.step_interval) && isNumber(value.cycle_delay) && typeof value.error_policy === 'string' && typeof value.decision_engine === 'string'
const isControlCycleResult = (value: unknown): value is ControlCycleResult => isRecord(value) && isNumber(value.cycle) && isNumber(value.simulation_time) && isControlMode(value.mode) && isTrafficSnapshot(value.states) && isNumber(value.actions_attempted) && Array.isArray(value.action_results) && value.action_results.every(isRecord) && Array.isArray(value.errors) && value.errors.every((error) => typeof error === 'string') && typeof value.success === 'boolean'

export async function getHealth() { const data = await request('/health'); if (!isHealthResponse(data)) throw new BackendRequestError('Unexpected /health response.'); return data }
export async function getIntersections() { const data = await request('/api/intersections'); if (!Array.isArray(data) || !data.every((id) => typeof id === 'string')) throw new BackendRequestError('Unexpected /api/intersections response.'); return data }
export async function getTrafficSnapshot(): Promise<TrafficSnapshot> { const data = await request('/api/traffic-state'); if (!isTrafficSnapshot(data)) throw new BackendRequestError('Unexpected /api/traffic-state response.'); return data }
export async function getVehicleSnapshot(): Promise<VehicleSnapshot> { const data = await request('/api/simulation/vehicles'); if (!isVehicleSnapshot(data)) throw new BackendRequestError('Unexpected /api/simulation/vehicles response.'); return data }
export async function getControlLoopStatus() { const data = await request('/api/control/loop/status'); if (!isControlLoopStatus(data)) throw new BackendRequestError('Unexpected /api/control/loop/status response.'); return data }
export async function getControlMode(): Promise<ControlModeResponse> { const data = await request('/api/control/mode'); if (!isControlModeResponse(data)) throw new BackendRequestError('Unexpected /api/control/mode response.'); return data }
export async function setControlMode(mode: ControlMode): Promise<ControlModeResponse> {
  const data = await request('/api/control/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) })
  if (!isControlModeResponse(data)) throw new BackendRequestError('Unexpected /api/control/mode response.')
  return data
}
export async function applyManualSignalTiming(action: ManualSignalAction): Promise<SignalActuationResult> {
  const controller = new AbortController()
  const timeout = globalThis.setTimeout(() => controller.abort(), 10_000)
  try {
    const data = await request('/api/control/signal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(action), signal: controller.signal })
    if (!isSignalActuationResult(data)) throw new BackendRequestError('Unexpected /api/control/signal response.')
    return data
  } finally { globalThis.clearTimeout(timeout) }
}
export async function stepControlLoop() { const data = await request('/api/control/loop/step', { method: 'POST' }); if (!isControlCycleResult(data)) throw new BackendRequestError('Unexpected /api/control/loop/step response.'); return data }
