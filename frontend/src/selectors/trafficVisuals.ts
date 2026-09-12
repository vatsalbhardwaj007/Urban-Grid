import type { Road, TrafficStatus } from '../types/digitalTwin'
import type { SignalPhase, TrafficSnapshot, TrafficState } from '../types/traffic'

export type IntersectionVisualState = { congestion: number; status: TrafficStatus; queue: number; meanSpeed: number; density: number; totalVehicles: number; phase: SignalPhase; greenRemaining: number }

export function selectIntersectionVisual(state: TrafficState | undefined): IntersectionVisualState {
  if (!state) return { congestion: 0, status: 'flowing', queue: 0, meanSpeed: 0, density: 0, totalVehicles: 0, phase: 'RED', greenRemaining: 0 }
  const totalVehicles = state.lane_features.reduce((total, lane) => total + lane.vehicle_count, 0)
  const queueScore = Math.min(state.total_queue / 12, 1)
  const densityScore = Math.min(state.density / 40, 1)
  const speedScore = state.mean_speed <= 0 ? 1 : 1 - Math.min(state.mean_speed / 13.9, 1)
  const congestion = Math.round((queueScore * .5 + densityScore * .3 + speedScore * .2) * 100)
  return { congestion, status: congestion >= 65 ? 'critical' : congestion >= 35 ? 'moderate' : 'flowing', queue: state.total_queue, meanSpeed: state.mean_speed, density: state.density, totalVehicles, phase: state.signal_phase, greenRemaining: state.green_remaining }
}

export function selectRoadStatus(road: Road, trafficByIntersection: TrafficSnapshot): TrafficStatus {
  const from = selectIntersectionVisual(trafficByIntersection[road.from])
  const to = selectIntersectionVisual(trafficByIntersection[road.to])
  const score = Math.max(from.congestion, to.congestion)
  return score >= 65 ? 'critical' : score >= 35 ? 'moderate' : 'flowing'
}

export function formatPhase(phase: SignalPhase) { return phase.charAt(0) + phase.slice(1).toLowerCase() }
