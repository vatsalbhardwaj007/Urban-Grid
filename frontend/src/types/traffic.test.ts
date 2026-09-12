import { describe, expect, it } from 'vitest'
import { isControlMode, isSignalActuationResult, isTrafficSnapshot, isTrafficState, parseWebSocketMessage } from './traffic'

const trafficUpdate = {
  event: 'traffic.update',
  data: {
    timestamp: 12,
    intersection_id: 'I1',
    lane_features: [{ lane_id: 'E_W1_I1_0', vehicle_count: 3, mean_speed: 8.45, queue_length: 1, occupancy: .12, arrival_rate: .5, density: 15, flow: 1800 }],
    total_queue: 1,
    mean_speed: 9.55,
    arrival_rate: .83,
    density: 6.25,
    signal_phase: 'GREEN',
    green_remaining: 14.5,
  },
}

describe('M2 TrafficState v1 parser', () => {
  it('preserves canonical uppercase signal phases', () => {
    const parsed = parseWebSocketMessage(trafficUpdate)
    expect(parsed).toEqual(trafficUpdate)
    expect(parsed?.event === 'traffic.update' && parsed.data.signal_phase).toBe('GREEN')
  })

  it('rejects malformed traffic data and noncanonical phases', () => {
    expect(isTrafficState({ ...trafficUpdate.data, signal_phase: 'green' })).toBe(false)
    expect(isTrafficState({ ...trafficUpdate.data, total_queue: 1.5 })).toBe(false)
    expect(isTrafficState({ ...trafficUpdate.data, lane_features: [{ ...trafficUpdate.data.lane_features[0], vehicle_count: -1 }] })).toBe(false)
    expect(isTrafficSnapshot([])).toBe(false)
    expect(parseWebSocketMessage({ event: 'traffic.update', data: { intersection_id: 'I1' } })).toBeNull()
    expect(parseWebSocketMessage({ event: 'other.update', data: trafficUpdate.data })).toBeNull()
  })

  it('only promotes a generic loop result when it is an actual signal result', () => {
    expect(isSignalActuationResult({ success: true, target: 'I1', applied_duration: 20, current_phase: 'GREEN', applied_to: 'active_green', source: 'AI', message: 'Applied.' })).toBe(true)
    expect(isSignalActuationResult({ success: true, target: 'veh-1', applied_route: ['e1'], previous_route: ['e0'], source: 'AI', message: 'Rerouted.' })).toBe(false)
  })

  it('accepts only the canonical M2 control modes', () => {
    expect(isControlMode('AUTO')).toBe(true)
    expect(isControlMode('MANUAL')).toBe(true)
    expect(isControlMode('EMERGENCY')).toBe(true)
    expect(isControlMode('auto')).toBe(false)
  })
})
