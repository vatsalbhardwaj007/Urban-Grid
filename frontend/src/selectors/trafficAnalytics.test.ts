import { describe, expect, it } from 'vitest'
import { aggregateTraffic, historyForScope, missingIntervals } from './trafficAnalytics'
import type { AnalyticsObservation } from '../state/trafficStore'
import type { TrafficState } from '../types/traffic'

function state(id: string, timestamp: number, queue = 0, vehicles = 0, speed = 0): TrafficState { return { timestamp, intersection_id: id, lane_features: [{ lane_id: `${id}_0`, vehicle_count: vehicles, mean_speed: speed, queue_length: queue, occupancy: .4, arrival_rate: 1, density: 5, flow: 20 }], total_queue: queue, mean_speed: speed, arrival_rate: 1, density: 5, signal_phase: 'GREEN', green_remaining: 8 } }
function observation(id: string, timestamp: number, queue = 0, vehicles = 0, speed = 0): AnalyticsObservation { return { intersectionId: id, simulationTime: timestamp, receivedAt: timestamp * 1000, source: 'websocket', state: state(id, timestamp, queue, vehicles, speed) } }

describe('traffic analytics selectors', () => {
  it('aggregates supported network metrics with vehicle-weighted speed', () => {
    const metrics = aggregateTraffic({ I1: state('I1', 4, 2, 2, 10), I2: state('I2', 4, 4, 6, 5) }, 'NETWORK')!
    expect(metrics).toMatchObject({ totalQueue: 6, averageQueue: 3, maximumQueue: 4, observedVehicles: 8, averageSpeed: 6.25, averageDensity: 5, arrivalRate: 2 })
  })

  it('limits intersection analytics to the selected canonical intersection', () => {
    expect(aggregateTraffic({ I1: state('I1', 4, 3, 2, 9), I2: state('I2', 4, 8, 7, 3) }, 'I1')).toMatchObject({ totalQueue: 3, maximumQueue: 3, observedVehicles: 2, averageSpeed: 9 })
  })

  it('preserves zero traffic as a measured zero rather than missing telemetry', () => {
    expect(aggregateTraffic({ I1: state('I1', 4) }, 'I1')).toMatchObject({ totalQueue: 0, observedVehicles: 0, averageSpeed: 0 })
    expect(aggregateTraffic({}, 'I1')).toBeNull()
  })

  it('creates a network history point only from a complete real timestamp', () => {
    const records = ['I1', 'I2', 'I3', 'I4'].map((id) => observation(id, 10, 1, 1, 8)).concat(observation('I1', 11, 2, 2, 7))
    expect(historyForScope(records, 'NETWORK')).toHaveLength(1)
    expect(historyForScope(records, 'I1').map((point) => point.simulationTime)).toEqual([10, 11])
  })

  it('orders history by simulation time and marks missing time intervals', () => {
    const points = historyForScope([observation('I1', 8), observation('I1', 10), observation('I1', 11), observation('I1', 15)], 'I1')
    expect(points.map((point) => point.simulationTime)).toEqual([8, 10, 11, 15])
    expect(missingIntervals(points)).toEqual([{ after: 11, before: 15 }])
  })

  it('does not expose a fabricated baseline or improvement field', () => {
    expect(aggregateTraffic({ I1: state('I1', 4) }, 'I1')).not.toHaveProperty('baselineImprovement')
  })
})
