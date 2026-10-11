import { describe, expect, it } from 'vitest'
import { initialTrafficStoreState, trafficStoreReducer } from './trafficStore'
import type { ControlLoopStatus, HealthResponse, SignalActuationResult, TrafficSnapshot, TrafficState, VehicleSnapshot } from '../types/traffic'

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
function vehicles(timestamp: number, ids = ['car-1']): VehicleSnapshot { return { timestamp, vehicles: ids.map((id, index) => ({ id, x: 250 + index, y: 750, speed: 8, angle: 90, lane_id: 'W_E1_I1_0', road_id: 'W_E1_I1', vehicle_type: 'passenger' })) } }

function bootstrapped(snapshotToLoad = snapshot(10, 1)) {
  return trafficStoreReducer(initialTrafficStoreState, { type: 'BOOTSTRAP', health, intersections: ['I1'], snapshot: snapshotToLoad, vehicles: vehicles(10), loopStatus, controlMode: 'AUTO' })
}

describe('traffic store REST fallback generations', () => {
  it('ignores a late REST response after a WebSocket reconnect', () => {
    const disconnected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_CLOSE' })
    const polling = trafficStoreReducer(disconnected, { type: 'POLL_SESSION_START', generation: 1 })
    const reconnected = trafficStoreReducer(trafficStoreReducer(polling, { type: 'POLL_INVALIDATED', generation: 2 }), { type: 'SOCKET_OPEN' })
    const websocketState = trafficStoreReducer(reconnected, { type: 'UPSERT', traffic: traffic(12, 9) })

    const afterLatePoll = trafficStoreReducer(websocketState, { type: 'POLL_SUCCESS', generation: 1, snapshot: snapshot(10, 1), vehicles: vehicles(10) })

    expect(afterLatePoll).toBe(websocketState)
    expect(afterLatePoll.trafficByIntersection.I1.total_queue).toBe(9)
    expect(afterLatePoll.lastSimulationTimestamp).toBe(12)
  })

  it('applies the active REST fallback snapshot while WebSocket is disconnected', () => {
    const disconnected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_CLOSE' })
    const polling = trafficStoreReducer(disconnected, { type: 'POLL_SESSION_START', generation: 1 })

    const afterPoll = trafficStoreReducer(polling, { type: 'POLL_SUCCESS', generation: 1, snapshot: snapshot(11, 6), vehicles: vehicles(11, ['rest-car']) })

    expect(afterPoll.trafficByIntersection.I1.total_queue).toBe(6)
    expect(afterPoll.lastSimulationTimestamp).toBe(11)
    expect(afterPoll.status).toBe('rest-fallback')
    expect(Object.keys(afterPoll.vehiclesById)).toEqual(['rest-car'])
  })

  it('accepts an authoritative reconnect resync while WebSocket is connected', () => {
    const connected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_OPEN' })

    const resynced = trafficStoreReducer(connected, { type: 'RESYNC', health, snapshot: snapshot(14, 4), vehicles: vehicles(14), loopStatus, controlMode: 'AUTO' })

    expect(resynced.trafficByIntersection.I1.total_queue).toBe(4)
    expect(resynced.lastSimulationTimestamp).toBe(14)
  })

  it('accepts a lower SUMO timestamp from an authoritative restart resync', () => {
    const connected = trafficStoreReducer(bootstrapped(snapshot(100, 8)), { type: 'SOCKET_OPEN' })

    const restarted = trafficStoreReducer(connected, { type: 'RESYNC', health: { ...health, simulation_time: 1 }, snapshot: snapshot(1, 2), vehicles: vehicles(1), loopStatus, controlMode: 'AUTO' })

    expect(restarted.trafficByIntersection.I1.timestamp).toBe(1)
    expect(restarted.lastSimulationTimestamp).toBe(1)
    expect(restarted.trafficByIntersection.I1.total_queue).toBe(2)
  })

  it('replaces the complete fleet by stable ID and retains only the prior real transform for interpolation', () => {
    const initial = bootstrapped()
    const updated = trafficStoreReducer(initial, { type: 'VEHICLE_SNAPSHOT', snapshot: { timestamp: 11, vehicles: [{ ...vehicles(11).vehicles[0], x: 300 }, vehicles(11, ['car-2']).vehicles[0] ] } })
    const replaced = trafficStoreReducer(updated, { type: 'VEHICLE_SNAPSHOT', snapshot: vehicles(12, ['car-1']) })

    expect(Object.keys(replaced.vehiclesById)).toEqual(['car-1'])
    expect(replaced.vehiclesById['car-1'].previous.x).toBe(300)
    expect(replaced.vehiclesById['car-1'].vehicle.x).toBe(250)
    expect(replaced.vehicleSnapshotTimestamp).toBe(12)
  })

  it('does not let a reconnect REST fleet resync replace a newer WebSocket fleet', () => {
    const connected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_OPEN' })
    const websocketFleet = trafficStoreReducer(connected, { type: 'VEHICLE_SNAPSHOT', snapshot: vehicles(12, ['ws-car']) })
    const staleResync = trafficStoreReducer(websocketFleet, { type: 'RESYNC', health, snapshot: snapshot(12, 1), vehicles: vehicles(11, ['rest-car']), loopStatus, controlMode: 'AUTO', expectedVehicleRevision: 0 })

    expect(Object.keys(staleResync.vehiclesById)).toEqual(['ws-car'])
  })

  it('updates the displayed mode only after a confirmed control-mode response', () => {
    const updated = trafficStoreReducer(bootstrapped(), { type: 'CONTROL_MODE', mode: 'MANUAL' })

    expect(updated.loopStatus?.mode).toBe('MANUAL')
    expect(updated.error).toBeNull()
  })

  it('rejects delayed traffic and vehicle snapshots without replacing newer real telemetry', () => {
    const connected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_OPEN' })
    const newer = trafficStoreReducer(trafficStoreReducer(connected, { type: 'UPSERT', traffic: traffic(12, 9) }), { type: 'VEHICLE_SNAPSHOT', snapshot: vehicles(12, ['new-car']) })
    const delayedTraffic = trafficStoreReducer(newer, { type: 'UPSERT', traffic: traffic(11, 2) })
    const delayedVehicles = trafficStoreReducer(delayedTraffic, { type: 'VEHICLE_SNAPSHOT', snapshot: vehicles(11, ['old-car']) })

    expect(delayedVehicles.trafficByIntersection.I1.total_queue).toBe(9)
    expect(Object.keys(delayedVehicles.vehiclesById)).toEqual(['new-car'])
    expect(delayedVehicles.vehicleSnapshotTimestamp).toBe(12)
  })

  it('accepts equal timestamps as idempotent authoritative updates', () => {
    const current = trafficStoreReducer(bootstrapped(), { type: 'UPSERT', traffic: traffic(12, 1) })
    const equal = trafficStoreReducer(current, { type: 'UPSERT', traffic: traffic(12, 7) })

    expect(equal.trafficByIntersection.I1.total_queue).toBe(7)
  })

  it('retains a real fleet as stale until a newer REST fallback snapshot arrives', () => {
    const closed = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_CLOSE' })
    const polling = trafficStoreReducer(closed, { type: 'POLL_SESSION_START', generation: 1 })
    const restored = trafficStoreReducer(polling, { type: 'POLL_SUCCESS', generation: 1, snapshot: snapshot(11, 4), vehicles: vehicles(11, ['rest-car']) })

    expect(Object.keys(closed.vehiclesById)).toEqual(['car-1'])
    expect(closed.status).toBe('telemetry-stale')
    expect(Object.keys(restored.vehiclesById)).toEqual(['rest-car'])
    expect(restored.status).toBe('rest-fallback')
  })

  it('does not let an older REST fallback replace newer WebSocket data', () => {
    const connected = trafficStoreReducer(bootstrapped(), { type: 'SOCKET_OPEN' })
    const newer = trafficStoreReducer(trafficStoreReducer(connected, { type: 'UPSERT', traffic: traffic(13, 8) }), { type: 'VEHICLE_SNAPSHOT', snapshot: vehicles(13, ['ws-car']) })
    const polling = trafficStoreReducer(trafficStoreReducer(newer, { type: 'SOCKET_CLOSE' }), { type: 'POLL_SESSION_START', generation: 1 })
    const afterOldRest = trafficStoreReducer(polling, { type: 'POLL_SUCCESS', generation: 1, snapshot: snapshot(12, 3), vehicles: vehicles(12, ['rest-car']) })

    expect(afterOldRest.trafficByIntersection.I1.total_queue).toBe(8)
    expect(Object.keys(afterOldRest.vehiclesById)).toEqual(['ws-car'])
    expect(afterOldRest.status).toBe('rest-fallback')
  })

  it('keeps complete signal and route action results from a control cycle', () => {
    const signal: SignalActuationResult = { success: true, target: 'I1', applied_duration: 20, current_phase: 'GREEN', applied_to: 'active_green', source: 'AI', message: 'Applied.' }
    const route = { success: true, target: 'veh-1', applied_route: ['e1'], previous_route: ['e0'], source: 'AI', message: 'Rerouted.' }
    const initial = bootstrapped()
    const stepped = trafficStoreReducer(initial, { type: 'LOOP_STEP', snapshot: snapshot(11, 2), mode: 'AUTO', intervention: signal, cycle: { cycle: 1, simulationTime: 11, mode: 'AUTO', actionsAttempted: 2, success: true, errors: [], actionResults: [{ ...signal }, route] }, expectedModeRevision: initial.modeRevision })

    expect(stepped.lastControlCycle?.actionResults).toEqual([signal, route])
    expect(stepped.controlCycleHistory).toHaveLength(1)
  })

  it('does not let a poll that began before a confirmed mode command overwrite it', () => {
    const commanded = trafficStoreReducer(bootstrapped(), { type: 'CONTROL_MODE', mode: 'EMERGENCY' })
    const stalePoll = trafficStoreReducer(commanded, { type: 'MODE_SYNC', mode: 'AUTO', expectedRevision: commanded.modeRevision - 1 })

    expect(stalePoll.controlMode).toBe('EMERGENCY')
  })

  it('retains a newer confirmed mode when an older control-loop response arrives', () => {
    const commanded = trafficStoreReducer(bootstrapped(), { type: 'CONTROL_MODE', mode: 'EMERGENCY' })
    const staleCycle = trafficStoreReducer(commanded, { type: 'LOOP_STEP', snapshot: snapshot(11, 2), mode: 'AUTO', intervention: null, cycle: { cycle: 2, simulationTime: 11, mode: 'AUTO', actionsAttempted: 0, success: true, errors: [], actionResults: [] }, expectedModeRevision: commanded.modeRevision - 1 })

    expect(staleCycle.controlMode).toBe('EMERGENCY')
    expect(staleCycle.lastControlCycle?.mode).toBe('AUTO')
  })
})
