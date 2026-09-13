import { describe, expect, it } from 'vitest'
import { selectIntersectionVisual, selectRoadStatus } from './trafficVisuals'

const highQueue = { timestamp: 1, intersection_id: 'I1', lane_features: [{ lane_id: 'lane-1', vehicle_count: 10, mean_speed: 1, queue_length: 9, occupancy: .8, arrival_rate: 1, density: 36, flow: 800 }], total_queue: 10, mean_speed: 1, arrival_rate: 1, density: 36, signal_phase: 'RED' as const, green_remaining: 0 }
const lowQueue = { ...highQueue, intersection_id: 'I2', total_queue: 0, mean_speed: 13.5, density: 0, signal_phase: 'GREEN' as const, green_remaining: 12 }

describe('traffic visual selectors', () => {
  it('derives a rendering status without changing canonical values', () => {
    const visual = selectIntersectionVisual(highQueue)
    expect(visual.status).toBe('critical')
    expect(visual.phase).toBe('RED')
  })

  it('uses endpoint congestion for road visual status', () => {
    expect(selectRoadStatus({ id: 'I1-I2', from: 'I1', to: 'I2', lanes: 2 }, { I1: highQueue, I2: lowQueue })).toBe('critical')
  })
})
