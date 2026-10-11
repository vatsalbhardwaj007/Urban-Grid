import { describe, expect, it } from 'vitest'
import { filterActionHistory } from '../components/layout/ActionHistory'
import { initialTrafficStoreState, trafficStoreReducer } from './trafficStore'

const signal = (target = 'I1') => ({ success: true, target, applied_duration: 30, current_phase: 'GREEN', applied_to: 'active_green', source: 'AI', message: 'Applied.' })
const route = { success: true, target: 'veh-1', applied_route: ['e1'], previous_route: ['e0'], source: 'AI', message: 'Rerouted.' }
const cycle = (results: Record<string, unknown>[]) => ({ type: 'LOOP_STEP' as const, snapshot: {}, mode: 'AUTO' as const, intervention: null, expectedModeRevision: 0, cycle: { cycle: 1, simulationTime: 1, mode: 'AUTO' as const, actionsAttempted: results.length, success: true, errors: [], actionResults: results } })

describe('session action history', () => {
  it('records signal, route, mixed, and repeated legitimate control-loop outcomes in order', () => {
    const state = trafficStoreReducer(initialTrafficStoreState, cycle([signal(), signal('I2'), route]))
    expect(state.actionHistory.map((record) => record.kind)).toEqual(['SIGNAL', 'SIGNAL', 'ROUTE'])
    expect(state.actionHistory.map((record) => record.target)).toEqual(['I1', 'I2', 'veh-1'])
    const repeated = trafficStoreReducer(state, cycle([signal(), signal()]))
    expect(repeated.actionHistory).toHaveLength(5)
    expect(repeated.actionHistory[0].target).toBe('I1')
  })
  it('retains client-observed provenance and missing backend fields without inventing data', () => {
    const state = trafficStoreReducer(initialTrafficStoreState, cycle([{ message: 'Partial backend result.' }]))
    expect(state.actionHistory[0]).toMatchObject({ kind: 'UNKNOWN', source: null, target: null, success: null, provenance: 'client-observed' })
  })
  it('keeps only the newest 100 records and evicts the oldest', () => {
    let state = initialTrafficStoreState
    for (let index = 0; index < 101; index += 1) state = trafficStoreReducer(state, cycle([signal(`I${index}`)]))
    expect(state.actionHistory).toHaveLength(100)
    expect(state.actionHistory.at(-1)?.target).toBe('I1')
    expect(state.actionHistory[0].target).toBe('I100')
  })
  it('filters type and backend-confirmed outcome while preserving empty states', () => {
    const state = trafficStoreReducer(initialTrafficStoreState, cycle([signal(), { ...route, success: false }]))
    expect(filterActionHistory(state.actionHistory, 'SIGNAL', 'SUCCESS')).toHaveLength(1)
    expect(filterActionHistory(state.actionHistory, 'ROUTE', 'FAILURE')).toHaveLength(1)
    expect(filterActionHistory(state.actionHistory, 'ROUTE', 'SUCCESS')).toEqual([])
  })
})
