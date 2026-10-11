/**
 * Mapping from the real SUMO network (0…1000 metres) to the existing schematic
 * Digital Twin.  The two networks have the same I1–I4 topology but intentionally
 * different visual proportions: approach roads are longer in the city scene than
 * internal links.  These anchors map every SUMO junction and boundary endpoint
 * onto its matching rendered road; no vehicle positions are hand-placed.
 */

export type WorldPoint = { x: number; z: number }

type Anchor = readonly [sumo: number, world: number]

const xAnchors: readonly Anchor[] = [[0, -29], [250, -11], [750, 11], [1000, 29]]
const yAnchors: readonly Anchor[] = [[0, -27], [250, -9], [750, 9], [1000, 27]]

function mapAnchoredCoordinate(value: number, anchors: readonly Anchor[]) {
  const clamped = Math.max(anchors[0][0], Math.min(anchors.at(-1)![0], value))
  for (let index = 1; index < anchors.length; index += 1) {
    const [nextSumo, nextWorld] = anchors[index]
    const [previousSumo, previousWorld] = anchors[index - 1]
    if (clamped <= nextSumo) {
      const ratio = (clamped - previousSumo) / (nextSumo - previousSumo)
      return previousWorld + (nextWorld - previousWorld) * ratio
    }
  }
  return anchors.at(-1)![1]
}

/** Transform a real SUMO (x,y) position into the Three.js ground plane (x,z). */
export function sumoToWorld(x: number, y: number): WorldPoint {
  return { x: mapAnchoredCoordinate(x, xAnchors), z: mapAnchoredCoordinate(y, yAnchors) }
}

/**
 * SUMO headings are degrees clockwise from north.  Three.js y-rotation uses a
 * model whose forward axis is +x, with north represented by +z in our scene.
 */
export function sumoAngleToWorldRotation(angle: number) {
  return angle * Math.PI / 180 - Math.PI / 2
}

export function interpolateWorldAngle(from: number, to: number, progress: number) {
  const difference = Math.atan2(Math.sin(to - from), Math.cos(to - from))
  return from + difference * Math.max(0, Math.min(1, progress))
}
