import { afterEach, describe, expect, it, vi } from 'vitest'
import { backendConfig } from '../config/backend'
import { selectIntersectionVisual } from '../selectors/trafficVisuals'
import { initialTrafficStoreState, trafficStoreReducer } from '../state/trafficStore'
import type { TrafficState } from '../types/traffic'
import { openTrafficSocket } from './trafficSocket'

class SocketHarness {
  readonly url: string
  constructor(url: string) { this.url = url }
}

function traffic(intersectionId: string, phase: TrafficState['signal_phase'] = 'GREEN'): TrafficState {
  return {
    timestamp: 40,
    intersection_id: intersectionId,
    lane_features: [{ lane_id: `${intersectionId}_approach_0`, vehicle_count: 3, mean_speed: 12, queue_length: 0, occupancy: .1, arrival_rate: .5, density: 6, flow: 1800 }],
    total_queue: 0,
    mean_speed: 12,
    arrival_rate: .5,
    density: 6,
    signal_phase: phase,
    green_remaining: 10,
  }
}

function handlers() {
  return { onOpen: vi.fn(), onUpdate: vi.fn(), onPong: vi.fn(), onMalformed: vi.fn(), onClose: vi.fn(), onError: vi.fn() }
}

function receive(socket: WebSocket, data: string) {
  socket.onmessage?.call(socket, new MessageEvent('message', { data }))
}

afterEach(() => { vi.unstubAllGlobals() })

describe('live traffic transport to centralized state', () => {
  it('forwards I1–I4 wire events and replaces only the affected intersection for visual selectors', () => {
    vi.stubGlobal('WebSocket', SocketHarness)
    const ids = ['I1', 'I2', 'I3', 'I4']
    let state = trafficStoreReducer(initialTrafficStoreState, {
      type: 'BOOTSTRAP',
      health: { status: 'ok', simulation_connected: true, simulation_time: 0 },
      intersections: ids,
      snapshot: {},
      loopStatus: null,
    })
    const callbacks = handlers()
    callbacks.onUpdate.mockImplementation((update: TrafficState) => {
      state = trafficStoreReducer(state, { type: 'UPSERT', traffic: update })
    })
    const socket = openTrafficSocket(callbacks)
    expect(socket.url).toBe(backendConfig.wsUrl)

    ids.forEach((id) => receive(socket, JSON.stringify({ event: 'traffic.update', data: traffic(id) })))
    expect(Object.keys(state.trafficByIntersection)).toEqual(ids)
    const unchangedI2 = state.trafficByIntersection.I2
    expect(selectIntersectionVisual(state.trafficByIntersection.I1).status).toBe('flowing')

    const redSignal = traffic('I1', 'RED')
    const congested = {
      ...redSignal,
      timestamp: 41,
      lane_features: [{ ...redSignal.lane_features[0], vehicle_count: 16, queue_length: 12, density: 40, mean_speed: 1, occupancy: .8 }],
      total_queue: 12,
      density: 40,
      mean_speed: 1,
      green_remaining: 0,
    }
    receive(socket, JSON.stringify({ event: 'traffic.update', data: congested }))

    expect(callbacks.onUpdate).toHaveBeenCalledTimes(5)
    expect(callbacks.onMalformed).not.toHaveBeenCalled()
    expect(state.trafficByIntersection.I1).toEqual(congested)
    expect(state.trafficByIntersection.I2).toBe(unchangedI2)
    expect(state.status).toBe('connected')
    expect(state.lastSimulationTimestamp).toBe(41)
    expect(state.lastReceivedAt).not.toBeNull()
    expect(selectIntersectionVisual(state.trafficByIntersection.I1)).toMatchObject({ status: 'critical', phase: 'RED', queue: 12, meanSpeed: 1 })
  })

  it('handles pong separately and rejects invalid wire data without forwarding it', () => {
    vi.stubGlobal('WebSocket', SocketHarness)
    const callbacks = handlers()
    const socket = openTrafficSocket(callbacks)

    receive(socket, JSON.stringify({ event: 'pong' }))
    receive(socket, '{invalid json')
    receive(socket, JSON.stringify({ event: 'traffic.update', data: { ...traffic('I1'), signal_phase: 'green' } }))
    receive(socket, JSON.stringify({ event: 'unrecognized.update', data: traffic('I1') }))

    expect(callbacks.onPong).toHaveBeenCalledOnce()
    expect(callbacks.onMalformed).toHaveBeenCalledTimes(3)
    expect(callbacks.onUpdate).not.toHaveBeenCalled()
  })

  it('lets the canonical store reject unknown intersection IDs without losing monitored data', () => {
    vi.stubGlobal('WebSocket', SocketHarness)
    let state = trafficStoreReducer(initialTrafficStoreState, {
      type: 'BOOTSTRAP',
      health: { status: 'ok', simulation_connected: true, simulation_time: 40 },
      intersections: ['I1'],
      snapshot: { I1: traffic('I1') },
      loopStatus: null,
    })
    const previousTraffic = state.trafficByIntersection
    const callbacks = handlers()
    callbacks.onUpdate.mockImplementation((update: TrafficState) => {
      state = trafficStoreReducer(state, { type: 'UPSERT', traffic: update })
    })

    receive(openTrafficSocket(callbacks), JSON.stringify({ event: 'traffic.update', data: traffic('I99') }))

    expect(state.unknownEvents).toBe(1)
    expect(state.trafficByIntersection).toBe(previousTraffic)
    expect(callbacks.onMalformed).not.toHaveBeenCalled()
  })
})
