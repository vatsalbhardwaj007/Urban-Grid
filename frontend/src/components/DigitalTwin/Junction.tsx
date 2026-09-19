import { memo, useLayoutEffect, useRef } from 'react'
import { InstancedMesh, Object3D } from 'three'
import type { Junction as JunctionDefinition, TrafficVisualStatus } from '../../types/digitalTwin'

const statusColors: Record<TrafficVisualStatus, string> = { flowing: '#55cc9d', moderate: '#e8b85e', critical: '#ee766b', unknown: '#36525c' }

const Crosswalks = memo(function Crosswalks() {
  const mesh = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const object = new Object3D()
    for (let side = 0; side < 4; side += 1) {
      const angle = side * Math.PI / 2
      for (let stripe = 0; stripe < 8; stripe += 1) {
        const cross = -1.95 + stripe * .56
        object.position.set(Math.cos(angle) * 3.22 - Math.sin(angle) * cross, .123, Math.sin(angle) * 3.22 + Math.cos(angle) * cross)
        object.rotation.y = -angle
        object.updateMatrix()
        mesh.current?.setMatrixAt(side * 8 + stripe, object.matrix)
      }
    }
    if (mesh.current) mesh.current.instanceMatrix.needsUpdate = true
  }, [])
  return <instancedMesh ref={mesh} args={[undefined, undefined, 32]}><boxGeometry args={[.7, .02, .3]} /><meshBasicMaterial color="#b7c2c1" /></instancedMesh>
})

export const Junction = memo(function Junction({ junction, status, totalQueue, selected, onSelect }: { junction: JunctionDefinition; status: TrafficVisualStatus; totalQueue: number; selected: boolean; onSelect: (id: string) => void }) {
  const statusColor = statusColors[status]
  const queueFill = Math.min(totalQueue / 24, 1)
  return <group position={[junction.x, 0, junction.z]} onClick={(event) => { event.stopPropagation(); onSelect(junction.id) }}>
    <mesh position={[0, .087, 0]}><boxGeometry args={[5.42, .04, 5.42]} /><meshStandardMaterial color={selected ? '#2a3b43' : '#202c34'} roughness={.96} /></mesh>
    <Crosswalks />
    {[[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([x, z], index) => <group key={index} position={[x * 2.85, .12, z * 2.85]}>
      <mesh><boxGeometry args={[.58, .13, .58]} /><meshStandardMaterial color="#526369" roughness={1} /></mesh>
      <mesh position={[0, .085, 0]}><boxGeometry args={[.36, .025, .36]} /><meshBasicMaterial color={statusColor} /></mesh>
    </group>)}
    {/* A small, explicitly aggregate gauge; no generated individual vehicle locations. */}
    {status !== 'unknown' && <group position={[0, .123, -1.8]}>
      <mesh><boxGeometry args={[2.8, .015, .18]} /><meshBasicMaterial color="#35434a" /></mesh>
      {queueFill > 0 && <mesh position={[-1.4 + queueFill * 1.4, .009, 0]}><boxGeometry args={[2.8 * queueFill, .02, .18]} /><meshBasicMaterial color={statusColor} /></mesh>}
    </group>}
    {selected && <>
      <mesh rotation={[-Math.PI / 2, 0, Math.PI / 4]} position={[0, .125, 0]}><ringGeometry args={[1.6, 1.65, 4]} /><meshBasicMaterial color="#78d7e0" transparent opacity={.7} /></mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, .129, 0]}><circleGeometry args={[.16, 16]} /><meshBasicMaterial color="#a8f0f1" /></mesh>
    </>}
  </group>
})
