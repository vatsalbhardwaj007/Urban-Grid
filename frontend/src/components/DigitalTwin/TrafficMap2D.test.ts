import { describe, expect, it, vi } from 'vitest'
import { CANONICAL_INTERSECTION_IDS, urbanGridTopology } from '../../data/urbanGridTopology'
import { activateTrafficMapIntersection, signalColor, trafficMapPoints, trafficMapRoads, trafficMapTelemetry, TRAFFIC_MAP_VIEW_BOX } from './TrafficMap2D'

const sample = { timestamp: 12, intersection_id: 'I1', lane_features: [{ lane_id: 'I1_0', vehicle_count: 0, mean_speed: 13.9, queue_length: 0, occupancy: 0, arrival_rate: 0, density: 0, flow: 0 }], total_queue: 0, mean_speed: 13.9, arrival_rate: 0, density: 0, signal_phase: 'GREEN' as const, green_remaining: 15 }

describe('TrafficMap2D', () => {
  it('uses exactly the canonical four intersection anchors', () => {
    expect(trafficMapPoints(urbanGridTopology.junctions).map((point) => point.id)).toEqual(CANONICAL_INTERSECTION_IDS)
    expect(TRAFFIC_MAP_VIEW_BOX).toBe('0 0 320 224')
  })

  it('draws only the canonical road connections', () => {
    expect(trafficMapRoads(urbanGridTopology.junctions, urbanGridTopology.roads, {}).map((road) => `${road.from.id}-${road.to.id}`)).toEqual(['I1-I2', 'I1-I3', 'I2-I4', 'I3-I4'])
  })

  it('maps actual signal and congestion telemetry without treating zero as absent', () => {
    const telemetry = trafficMapTelemetry(sample, 'connected')
    expect(telemetry).toMatchObject({ available: true, stale: false, queue: 0, congestion: 0, phase: 'GREEN', source: 'Live WebSocket' })
    expect(signalColor(telemetry.phase)).toBe('#76d9ad')
  })

  it('labels missing, stale, REST-fallback, and unavailable telemetry accurately', () => {
    expect(trafficMapTelemetry(undefined, 'connecting')).toMatchObject({ available: false, status: 'unknown', source: 'Awaiting telemetry' })
    expect(trafficMapTelemetry(sample, 'telemetry-stale')).toMatchObject({ available: true, stale: true, source: 'Last real snapshot · stale' })
    expect(trafficMapTelemetry(sample, 'reconnecting')).toMatchObject({ available: true, stale: true, source: 'Reconnecting · last real snapshot' })
    expect(trafficMapTelemetry(sample, 'rest-fallback')).toMatchObject({ available: true, stale: false, source: 'REST fallback' })
    expect(trafficMapTelemetry(sample, 'sumo-unavailable')).toMatchObject({ available: false, phase: null, source: 'SUMO unavailable' })
  })

  it('uses the existing selection callback for accessible map activation', () => {
    const select = vi.fn()
    activateTrafficMapIntersection('I3', select)
    expect(select).toHaveBeenCalledOnce()
    expect(select).toHaveBeenCalledWith('I3')
  })

  it('derives road severity from current snapshot endpoints', () => {
    const critical = { ...sample, intersection_id: 'I2', total_queue: 12, mean_speed: 0, density: 40, signal_phase: 'RED' as const }
    expect(trafficMapRoads(urbanGridTopology.junctions, urbanGridTopology.roads, { I1: sample, I2: critical }).find((road) => road.id === 'I1-I2')?.status).toBe('critical')
  })
})
