import { describe, expect, it } from 'vitest'
import { initialTrafficStoreState, trafficStoreReducer } from './trafficStore'
import type { ControlLoopStatus, HealthResponse, TrafficSnapshot, TrafficState } from '../types/traffic'

const health: HealthResponse = { status: 'ok', simulation_connected: true, simulation_time: 0 }
const loopStatus: ControlLoopStatus = { mode: 'AUTO', is_running: false, current_cycle: 0, step_interval: 1, cycle_delay: 0, error_policy: 'continue', decision_engine: 'NullDecisionEngine' }

function traffic(timestamp: number, totalQueue: number): TrafficState {
  return {
    timestamp,
    intersection_id: 'I1',
    lane_features: [{ lane_id: 'I1_lane', vehicle_count: totalQueue, mean_speed: 8, queue_length: totalQueue, occupancy: .2, arrival_rate: 1, density: 5, flow: 120 }],
    total_queue: totalQueue,
    mean_speed: 8,
    arrival_rate: 1,
    density: 5,
    signal_phase: 'GREEN',
    green_remaining: 12,
  }
}

function snapshot(timestamp: number, totalQueue: number): TrafficSnapshot { return { I1: traffic(timestamp, totalQueue) } }

function bootstrapped(snapshotToLoad = snapshot(10, 1)) {
  return trafficStoreReducer(initialTrafficStoreState, { type: 'BOOTSTRAP', health, intersections: ['I1'], snapshot: snapshotToLoad, loopStatus })
}

describe('traffic store REST fallback generations', () => {
  it('ignores a late REST response after a WebSocket reconnect', () => {
    const disconnected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_CLOSE' })
    const polling = trafficStoreReducer(disconnected, { type: 'POLL_SESSION_START', generation: 1 })
    const reconnected = trafficStoreReducer(trafficStoreReducer(polling, { type: 'POLL_INVALIDATED', generation: 2 }), { type: 'SOCKET_OPEN' })
    const websocketState = trafficStoreReducer(reconnected, { type: 'UPSERT', traffic: traffic(12, 9) })

    const afterLatePoll = trafficStoreReducer(websocketState, { type: 'POLL_SUCCESS', generation: 1, snapshot: snapshot(10, 1) })

    expect(afterLatePoll).toBe(websocketState)
    expect(afterLatePoll.trafficByIntersection.I1.total_queue).toBe(9)
    expect(afterLatePoll.lastSimulationTimestamp).toBe(12)
  })

  it('applies the active REST fallback snapshot while WebSocket is disconnected', () => {
    const disconnected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_CLOSE' })
    const polling = trafficStoreReducer(disconnected, { type: 'POLL_SESSION_START', generation: 1 })

    const afterPoll = trafficStoreReducer(polling, { type: 'POLL_SUCCESS', generation: 1, snapshot: snapshot(11, 6) })

    expect(afterPoll.trafficByIntersection.I1.total_queue).toBe(6)
    expect(afterPoll.lastSimulationTimestamp).toBe(11)
    expect(afterPoll.status).toBe('disconnected')
  })

  it('accepts an authoritative reconnect resync while WebSocket is connected', () => {
    const connected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_OPEN' })

    const resynced = trafficStoreReducer(connected, { type: 'RESYNC', health, snapshot: snapshot(14, 4), loopStatus })

    expect(resynced.trafficByIntersection.I1.total_queue).toBe(4)
    expect(resynced.lastSimulationTimestamp).toBe(14)
  })

  it('accepts a lower SUMO timestamp from an authoritative restart resync', () => {
    const connected = trafficStoreReducer(bootstrapped(snapshot(100, 8)), { type: 'SOCKET_OPEN' })

    const restarted = trafficStoreReducer(connected, { type: 'RESYNC', health: { ...health, simulation_time: 1 }, snapshot: snapshot(1, 2), loopStatus })

    expect(restarted.trafficByIntersection.I1.timestamp).toBe(1)
    expect(restarted.lastSimulationTimestamp).toBe(1)
    expect(restarted.trafficByIntersection.I1.total_queue).toBe(2)
  })
})
