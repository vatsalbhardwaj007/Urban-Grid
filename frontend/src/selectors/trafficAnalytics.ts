import { CANONICAL_INTERSECTION_IDS } from '../data/urbanGridTopology'
import type { AnalyticsObservation } from '../state/trafficStore'
import type { TrafficSnapshot, TrafficState } from '../types/traffic'

export type AnalyticsScope = 'NETWORK' | (typeof CANONICAL_INTERSECTION_IDS)[number]
export type AnalyticsPoint = { simulationTime: number; receivedAt: number; source: AnalyticsObservation['source']; observedIntersections: number; averageSpeed: number; totalQueue: number; averageQueue: number; maximumQueue: number; averageDensity: number; arrivalRate: number; observedVehicles: number; averageOccupancy: number | null }

function observationVehicles(state: TrafficState) { return state.lane_features.reduce((sum, lane) => sum + lane.vehicle_count, 0) }

/** Current aggregates use only canonical TrafficState fields; no trip completion or delay is inferred. */
export function aggregateTraffic(snapshot: TrafficSnapshot, scope: AnalyticsScope): AnalyticsPoint | null {
  const states = scope === 'NETWORK' ? CANONICAL_INTERSECTION_IDS.map((id) => snapshot[id]).filter((state): state is TrafficState => Boolean(state)) : snapshot[scope] ? [snapshot[scope]] : []
  if (!states.length) return null
  const observedVehicles = states.reduce((sum, state) => sum + observationVehicles(state), 0)
  const totalQueue = states.reduce((sum, state) => sum + state.total_queue, 0)
  const weightedSpeed = states.reduce((sum, state) => sum + state.mean_speed * observationVehicles(state), 0)
  const lanes = states.flatMap((state) => state.lane_features)
  return {
    simulationTime: Math.max(...states.map((state) => state.timestamp)),
    receivedAt: 0,
    source: 'websocket',
    observedIntersections: states.length,
    averageSpeed: observedVehicles > 0 ? weightedSpeed / observedVehicles : 0,
    totalQueue,
    averageQueue: totalQueue / states.length,
    maximumQueue: Math.max(...states.map((state) => state.total_queue)),
    averageDensity: states.reduce((sum, state) => sum + state.density, 0) / states.length,
    arrivalRate: states.reduce((sum, state) => sum + state.arrival_rate, 0),
    observedVehicles,
    averageOccupancy: lanes.length ? lanes.reduce((sum, lane) => sum + lane.occupancy, 0) / lanes.length : null,
  }
}

function pointFromStates(states: TrafficState[], observation: AnalyticsObservation): AnalyticsPoint {
  const snapshot = Object.fromEntries(states.map((state) => [state.intersection_id, state]))
  const aggregate = aggregateTraffic(snapshot, states.length === 1 ? states[0].intersection_id as AnalyticsScope : 'NETWORK')!
  return { ...aggregate, simulationTime: observation.simulationTime, receivedAt: observation.receivedAt, source: observation.source }
}

/**
 * Network points are emitted only when all four canonical intersections share an
 * actual simulation timestamp. This avoids inventing an aggregate from a mix of
 * different timesteps while individual intersection histories remain available.
 */
export function historyForScope(history: AnalyticsObservation[], scope: AnalyticsScope): AnalyticsPoint[] {
  if (scope !== 'NETWORK') return history.filter((observation) => observation.intersectionId === scope).sort((a, b) => a.simulationTime - b.simulationTime || a.receivedAt - b.receivedAt).map((observation) => pointFromStates([observation.state], observation))
  const byTime = new Map<number, Map<string, AnalyticsObservation>>()
  for (const observation of history) {
    const group = byTime.get(observation.simulationTime) ?? new Map<string, AnalyticsObservation>()
    group.set(observation.intersectionId, observation)
    byTime.set(observation.simulationTime, group)
  }
  return [...byTime.entries()].sort(([a], [b]) => a - b).flatMap(([, group]) => {
    const observations = CANONICAL_INTERSECTION_IDS.map((id) => group.get(id))
    if (observations.some((observation) => !observation)) return []
    const present = observations as AnalyticsObservation[]
    return [pointFromStates(present.map((observation) => observation.state), present.at(-1)!)]
  })
}

export function missingIntervals(points: AnalyticsPoint[]) {
  if (points.length < 3) return []
  const gaps = points.slice(1).map((point, index) => point.simulationTime - points[index].simulationTime).filter((gap) => gap > 0).sort((a, b) => a - b)
  const typical = gaps[Math.floor(gaps.length / 2)]
  if (!typical) return []
  return points.slice(1).flatMap((point, index) => point.simulationTime - points[index].simulationTime > typical * 1.5 ? [{ after: points[index].simulationTime, before: point.simulationTime }] : [])
}

export function scopeLabel(scope: AnalyticsScope) { return scope === 'NETWORK' ? 'Entire network' : scope }
export function formatSimulationTime(time: number) { return `t+${time.toFixed(1)} s` }
