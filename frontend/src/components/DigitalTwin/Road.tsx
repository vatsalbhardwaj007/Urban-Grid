import { memo, useLayoutEffect, useMemo, useRef } from 'react'
import { InstancedMesh, Object3D } from 'three'
import type { Junction, TrafficVisualStatus } from '../../types/digitalTwin'

const ROAD_HALF_WIDTH = 2.4
const statusColors: Record<TrafficVisualStatus, string> = { flowing: '#55cc9d', moderate: '#e8b85e', critical: '#ee766b', unknown: '#36525c' }

function LaneMarkings({ length }: { length: number }) {
  const mesh = useRef<InstancedMesh>(null)
  const markers = useMemo(() => {
    const count = Math.max(1, Math.floor((length - 2) / 1.9))
    return [-1.2, 1.2].flatMap((z) => Array.from({ length: count }, (_, i) => ({ x: -length / 2 + 1.2 + i * 1.9, z })))
  }, [length])
  useLayoutEffect(() => {
    const object = new Object3D()
    markers.forEach(({ x, z }, index) => {
      object.position.set(x, .113, z)
      object.updateMatrix()
      mesh.current?.setMatrixAt(index, object.matrix)
    })
    if (mesh.current) mesh.current.instanceMatrix.needsUpdate = true
  }, [markers])
  return <instancedMesh ref={mesh} args={[undefined, undefined, markers.length]}>
    <boxGeometry args={[.83, .014, .075]} />
    <meshBasicMaterial color="#a8b5b7" />
  </instancedMesh>
}

/** Neutral asphalt and lane markings are static; edge strips encode aggregate congestion. */
export const Road = memo(function Road({ from, to, status, approach = false }: { from: Pick<Junction, 'x' | 'z'>; to: Pick<Junction, 'x' | 'z'>; status: TrafficVisualStatus; approach?: boolean }) {
  const dx = to.x - from.x
  const dz = to.z - from.z
  const distance = Math.hypot(dx, dz)
  const angle = -Math.atan2(dz, dx)
  const startTrim = 2.7
  const endTrim = approach ? 0 : 2.7
  const length = Math.max(.1, distance - startTrim - endTrim)
  const offset = (startTrim - endTrim) / 2
  const cx = (from.x + to.x) / 2 + dx / distance * offset
  const cz = (from.z + to.z) / 2 + dz / distance * offset
  return <group position={[cx, 0, cz]} rotation={[0, angle, 0]}>
    <mesh position={[0, .055, 0]}><boxGeometry args={[length, .1, 6.65]} /><meshStandardMaterial color="#32444b" roughness={1} /></mesh>
    <mesh position={[0, .087, 0]}><boxGeometry args={[length, .04, ROAD_HALF_WIDTH * 2]} /><meshStandardMaterial color="#202c34" roughness={.96} /></mesh>
    {[-1, 1].map((side) => <group key={side}>
      <mesh position={[0, .115, side * 2.51]}><boxGeometry args={[length, .085, .2]} /><meshStandardMaterial color="#6a7b7f" roughness={1} /></mesh>
      <mesh position={[0, .113, side * 2.14]}><boxGeometry args={[length, .014, .065]} /><meshBasicMaterial color="#849498" /></mesh>
      <mesh position={[0, .126, side * 2.38]}><boxGeometry args={[length, .025, .12]} /><meshBasicMaterial color={statusColors[status]} transparent opacity={approach ? .25 : .85} /></mesh>
      <mesh position={[0, .113, side * .065]}><boxGeometry args={[length, .012, .035]} /><meshBasicMaterial color="#ad9c6a" /></mesh>
    </group>)}
    <LaneMarkings length={length} />
  </group>
})
