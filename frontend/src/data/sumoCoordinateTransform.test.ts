import { describe, expect, it } from 'vitest'
import { interpolateWorldAngle, sumoAngleToWorldRotation, sumoToWorld } from './sumoCoordinateTransform'

describe('SUMO to Digital Twin coordinate transform', () => {
  it('maps each real SUMO intersection onto its rendered I1–I4 counterpart', () => {
    expect(sumoToWorld(250, 750)).toEqual({ x: -11, z: 9 })
    expect(sumoToWorld(750, 750)).toEqual({ x: 11, z: 9 })
    expect(sumoToWorld(250, 250)).toEqual({ x: -11, z: -9 })
    expect(sumoToWorld(750, 250)).toEqual({ x: 11, z: -9 })
  })

  it('maps SUMO boundary roads to the existing city approaches', () => {
    expect(sumoToWorld(0, 750).x).toBe(-29)
    expect(sumoToWorld(1000, 750).x).toBe(29)
    expect(sumoToWorld(250, 0).z).toBe(-27)
    expect(sumoToWorld(250, 1000).z).toBe(27)
  })

  it('converts SUMO cardinal headings to the Three.js car model orientation', () => {
    expect(sumoAngleToWorldRotation(90)).toBeCloseTo(0) // east (+x)
    expect(sumoAngleToWorldRotation(0)).toBeCloseTo(-Math.PI / 2) // north (+z)
    expect(sumoAngleToWorldRotation(180)).toBeCloseTo(Math.PI / 2) // south (-z)
  })

  it('interpolates across the shortest heading arc', () => {
    const nearPi = Math.PI - .1
    const nearNegativePi = -Math.PI + .1
    expect(Math.abs(interpolateWorldAngle(nearPi, nearNegativePi, .5))).toBeCloseTo(Math.PI)
  })
})
