import { PerspectiveCamera, Vector3 } from 'three'
import { describe, expect, it } from 'vitest'
import { clampCameraDistance, clampPanTarget, getCameraPreset, getCityBounds, getCityPreset, MIN_CAMERA_DISTANCE } from './cameraPresets'

const junctions = [{ x: -11, z: 9 }, { x: 11, z: 9 }, { x: -11, z: -9 }, { x: 11, z: -9 }]

describe('Digital Twin camera framing', () => {
  it.each([.55, 1, 1.8, 2.5])('fits all four junctions and city context at aspect %s', (aspect) => {
    const bounds = getCityBounds(junctions)
    const preset = getCityPreset(bounds, aspect)
    const camera = new PerspectiveCamera(38, aspect, .1, 500)
    camera.position.set(...preset.position)
    camera.lookAt(...preset.target)
    camera.updateMatrixWorld()
    for (const x of [bounds.minX, bounds.maxX]) {
      for (const z of [bounds.minZ, bounds.maxZ]) {
        for (const y of [0, 9]) {
          const projected = new Vector3(x, y, z).project(camera)
          expect(Math.abs(projected.x)).toBeLessThan(1)
          expect(Math.abs(projected.y)).toBeLessThan(1)
          expect(projected.z).toBeLessThan(1)
        }
      }
    }
  })

  it('focuses each selected junction above ground and closer than overview', () => {
    const city = getCityPreset(getCityBounds(junctions), 1.5)
    const cityDistance = new Vector3(...city.position).distanceTo(new Vector3(...city.target))
    for (const selected of junctions) {
      const focus = getCameraPreset('junction', city, selected)
      expect(focus.target).toEqual([selected.x, 0, selected.z])
      expect(focus.position[1]).toBeGreaterThan(0)
      expect(new Vector3(...focus.position).distanceTo(new Vector3(...focus.target))).toBeLessThan(cityDistance)
    }
  })

  it('preserves building/local views and does not fabricate vehicle follow coordinates', () => {
    const city = getCityPreset(getCityBounds(junctions), 1.5)
    expect(getCameraPreset('building', city)).not.toEqual(city)
    expect(getCameraPreset('localTwin', city)).not.toEqual(city)
    expect(getCameraPreset('followVehicle', city)).toBe(city)
    expect(getCameraPreset('followVehicle', city, undefined, { x: 5, z: 7 }).target).toEqual([5, 0, 7])
  })

  it('keeps panning inside the city and clamps zoom to useful distances', () => {
    expect(clampPanTarget(-100, 200)).toEqual({ x: -28, z: 28 })
    expect(clampPanTarget(12, -8)).toEqual({ x: 12, z: -8 })
    expect(clampCameraDistance(1, 100)).toBe(MIN_CAMERA_DISTANCE)
    expect(clampCameraDistance(200, 100)).toBe(100)
    expect(clampCameraDistance(45, 100)).toBe(45)
  })
})
