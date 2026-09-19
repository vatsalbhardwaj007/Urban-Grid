import { Vector3 } from 'three'
import type { ViewMode } from '../../types/digitalTwin'

export type CameraPoint = { x: number; z: number }
export type CityBounds = { minX: number; maxX: number; minZ: number; maxZ: number }
export type CameraPreset = { position: [number, number, number]; target: [number, number, number] }

export const MIN_CAMERA_DISTANCE = 9
export const MAX_POLAR_ANGLE = Math.PI * .43
export const CITY_CONTEXT_PADDING = 13

/** Render-space bounds only. They never depend on traffic measurements. */
export function getCityBounds(junctions: CameraPoint[]): CityBounds {
  const points = junctions.length ? junctions : [{ x: -11, z: -9 }, { x: 11, z: 9 }]
  return {
    minX: Math.min(...points.map((point) => point.x)) - CITY_CONTEXT_PADDING,
    maxX: Math.max(...points.map((point) => point.x)) + CITY_CONTEXT_PADDING,
    minZ: Math.min(...points.map((point) => point.z)) - CITY_CONTEXT_PADDING,
    maxZ: Math.max(...points.map((point) => point.z)) + CITY_CONTEXT_PADDING,
  }
}

/** Fit both horizontal and vertical frusta, including roofs and floating labels. */
export function getCityPreset(bounds: CityBounds, aspect: number, fov = 38): CameraPreset {
  const target = new Vector3((bounds.minX + bounds.maxX) / 2, 0, (bounds.minZ + bounds.maxZ) / 2)
  const direction = new Vector3(.48, 1.1, .94).normalize()
  const right = new Vector3(0, 1, 0).cross(direction).normalize()
  const up = direction.clone().cross(right)
  const verticalTangent = Math.tan(fov * Math.PI / 360)
  const horizontalTangent = verticalTangent * Math.max(.25, aspect)
  let distance = MIN_CAMERA_DISTANCE
  for (const x of [bounds.minX, bounds.maxX]) {
    for (const y of [0, 9]) {
      for (const z of [bounds.minZ, bounds.maxZ]) {
        const point = new Vector3(x, y, z).sub(target)
        const depth = point.dot(direction)
        distance = Math.max(distance, depth + Math.abs(point.dot(right)) / horizontalTangent, depth + Math.abs(point.dot(up)) / verticalTangent)
      }
    }
  }
  return { position: target.clone().addScaledVector(direction, distance * 1.1).toArray(), target: target.toArray() }
}

export function getCameraPreset(mode: ViewMode, city: CameraPreset, selected?: CameraPoint, followed?: CameraPoint): CameraPreset {
  if (mode === 'junction' && selected) return { position: [selected.x + 10, 20, selected.z + 16], target: [selected.x, 0, selected.z] }
  if (mode === 'building') return { position: [25, 25, 31], target: [0, 2, 0] }
  if (mode === 'localTwin') return { position: [10, 20, 19], target: [0, 0, 0] }
  // A follow preset is available only when the caller supplies actual vehicle coordinates.
  if (mode === 'followVehicle' && followed) return { position: [followed.x + 6, 10, followed.z + 9], target: [followed.x, 0, followed.z] }
  return city
}

export function clampPanTarget(x: number, z: number): CameraPoint {
  return { x: Math.max(-28, Math.min(28, x)), z: Math.max(-28, Math.min(28, z)) }
}

export function clampCameraDistance(distance: number, maxDistance: number): number {
  return Math.max(MIN_CAMERA_DISTANCE, Math.min(maxDistance, distance))
}
