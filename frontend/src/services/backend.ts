import { backendConfig } from '../config/backend'
import type { ApiErrorResponse, ControlCycleResult, ControlLoopStatus, HealthResponse, TrafficSnapshot } from '../types/traffic'
import { isTrafficSnapshot } from '../types/traffic'

export class BackendRequestError extends Error {
  constructor(message: string, readonly status?: number) { super(message); this.name = 'BackendRequestError' }
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

function errorDetail(value: unknown) {
  if (!isRecord(value) || !('detail' in value)) return 'Backend request failed.'
  const detail = (value as ApiErrorResponse).detail
  return typeof detail === 'string' ? detail : detail.map((item) => item.msg).join('; ')
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  let response: Response
  try { response = await fetch(`${backendConfig.httpUrl}${path}`, { headers: { Accept: 'application/json', ...init?.headers }, ...init }) }
  catch { throw new BackendRequestError('Backend is unavailable.') }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new BackendRequestError(errorDetail(body), response.status)
  return body
}

const isHealthResponse = (value: unknown): value is HealthResponse => isRecord(value) && value.status === 'ok' && typeof value.simulation_connected === 'boolean' && (value.simulation_time === null || isNumber(value.simulation_time))
const isControlLoopStatus = (value: unknown): value is ControlLoopStatus => isRecord(value) && typeof value.is_running === 'boolean' && isNumber(value.current_cycle) && isNumber(value.step_interval) && isNumber(value.cycle_delay) && typeof value.error_policy === 'string' && typeof value.decision_engine === 'string'
const isControlCycleResult = (value: unknown): value is ControlCycleResult => isRecord(value) && isNumber(value.cycle) && isNumber(value.simulation_time) && isTrafficSnapshot(value.states) && isNumber(value.actions_attempted) && Array.isArray(value.action_results) && Array.isArray(value.errors) && value.errors.every((error) => typeof error === 'string') && typeof value.success === 'boolean'

export async function getHealth() { const data = await request('/health'); if (!isHealthResponse(data)) throw new BackendRequestError('Unexpected /health response.'); return data }
export async function getIntersections() { const data = await request('/api/intersections'); if (!Array.isArray(data) || !data.every((id) => typeof id === 'string')) throw new BackendRequestError('Unexpected /api/intersections response.'); return data }
export async function getTrafficSnapshot(): Promise<TrafficSnapshot> { const data = await request('/api/traffic-state'); if (!isTrafficSnapshot(data)) throw new BackendRequestError('Unexpected /api/traffic-state response.'); return data }
export async function getControlLoopStatus() { const data = await request('/api/control/loop/status'); if (!isControlLoopStatus(data)) throw new BackendRequestError('Unexpected /api/control/loop/status response.'); return data }
export async function stepControlLoop() { const data = await request('/api/control/loop/step', { method: 'POST' }); if (!isControlCycleResult(data)) throw new BackendRequestError('Unexpected /api/control/loop/step response.'); return data }
