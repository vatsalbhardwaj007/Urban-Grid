import { afterEach, describe, expect, it, vi } from 'vitest'
import { BackendRequestError, applyManualSignalTiming } from '../../services/backend'
import { manualSignalAvailability } from './ManualSignalControl'

const health = { status: 'ok' as const, simulation_connected: true, simulation_time: 10 }
const action = { target: 'I1', green_duration: 30, source: 'MANUAL' as const, timestamp: '2026-10-11T12:00:00.000Z' }
const confirmed = { success: true, target: 'I1', applied_duration: 30, current_phase: 'GREEN', applied_to: 'active_green', source: 'MANUAL', message: 'Applied.' }
const available = (overrides = {}) => manualSignalAvailability({ health, status: 'connected', mode: 'MANUAL', intersectionId: 'I1', intersectionAvailable: true, duration: 30, submitting: false, ...overrides })

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

describe('manual signal control safety', () => {
  it('permits only a valid MANUAL request with a selected intersection', () => expect(available()).toEqual({ enabled: true, reason: null }))
  it('rejects an invalid duration before a request is sent', () => expect(available({ duration: 4 })).toMatchObject({ enabled: false, reason: expect.stringContaining('5') }))
  it('rejects AUTO mode', () => expect(available({ mode: 'AUTO' })).toMatchObject({ enabled: false, reason: expect.stringContaining('AUTO') }))
  it('rejects EMERGENCY mode', () => expect(available({ mode: 'EMERGENCY' })).toMatchObject({ enabled: false, reason: expect.stringContaining('EMERGENCY') }))
  it('rejects unavailable backend or SUMO', () => {
    expect(available({ health: { ...health, simulation_connected: false } })).toMatchObject({ enabled: false })
    expect(available({ status: 'backend-unavailable' })).toMatchObject({ enabled: false })
  })
  it('prevents duplicate submissions and requires a selected intersection', () => {
    expect(available({ submitting: true })).toMatchObject({ enabled: false, reason: expect.stringContaining('already') })
    expect(available({ intersectionAvailable: false })).toMatchObject({ enabled: false, reason: expect.stringContaining('Select') })
  })
})

describe('POST /api/control/signal client', () => {
  it('sends a valid MANUAL payload and returns only a backend-confirmed result', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => confirmed })
    vi.stubGlobal('fetch', fetchMock)
    await expect(applyManualSignalTiming(action)).resolves.toEqual(confirmed)
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/api\/control\/signal$/), expect.objectContaining({ method: 'POST', body: JSON.stringify(action) }))
  })
  it('surfaces backend validation errors without inventing a success result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: [{ msg: 'Input should be greater than 0' }] }) }))
    await expect(applyManualSignalTiming(action)).rejects.toMatchObject<Partial<BackendRequestError>>({ message: 'Input should be greater than 0', status: 422 })
  })
  it('surfaces failed network requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))
    await expect(applyManualSignalTiming(action)).rejects.toMatchObject<Partial<BackendRequestError>>({ message: 'Backend is unavailable.' })
  })
})
