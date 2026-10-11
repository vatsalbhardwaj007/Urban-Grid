import { useFrame } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { Color, Group, InstancedMesh, Object3D, Vector3 } from 'three'
import { interpolateWorldAngle, sumoAngleToWorldRotation, sumoToWorld } from '../../data/sumoCoordinateTransform'
import type { VehicleTrack } from '../../types/traffic'

type VehicleFleetProps = {
  tracks: VehicleTrack[]
  selectedVehicleId: string | null
  onSelectVehicle: (id: string) => void
}

type AnimatedVehicle = {
  from: Vector3
  to: Vector3
  fromAngle: number
  toAngle: number
  startedAt: number
  durationMs: number
}

const vehiclePalette = ['#61d7ea', '#64d6a7', '#e8b85e', '#ef756a', '#74b7ea', '#d8945d']

function colorForVehicle(id: string) {
  let hash = 0
  for (const character of id) hash = (hash * 31 + character.charCodeAt(0)) | 0
  return vehiclePalette[Math.abs(hash) % vehiclePalette.length]
}

// The bundled SUMO scenario is well below this, while a fixed pool avoids
// reallocating GPU instance buffers whenever a vehicle enters or leaves.
const VEHICLE_CAPACITY = 1_024

/** High-contrast meshes keep normal-size real and demo fleets legible from the city overview. */
function VisibleVehicleMesh({ track, selected, onSelect }: { track: VehicleTrack; selected: boolean; onSelect: () => void }) {
  const group = useRef<Group>(null)
  const motion = useRef<{ from: Vector3; to: Vector3; fromAngle: number; toAngle: number; startedAt: number; durationMs: number } | null>(null)
  useEffect(() => {
    const now = performance.now()
    const previous = sumoToWorld(track.previous.x, track.previous.y)
    const current = sumoToWorld(track.vehicle.x, track.vehicle.y)
    motion.current = { from: new Vector3(previous.x, .46, previous.z), to: new Vector3(current.x, .46, current.z), fromAngle: sumoAngleToWorldRotation(track.previous.angle), toAngle: sumoAngleToWorldRotation(track.vehicle.angle), startedAt: now, durationMs: 260 }
  }, [track])
  useFrame(() => {
    const active = motion.current
    const node = group.current
    if (!active || !node) return
    const progress = Math.min(1, Math.max(0, (performance.now() - active.startedAt) / active.durationMs))
    node.position.lerpVectors(active.from, active.to, progress)
    node.rotation.y = interpolateWorldAngle(active.fromAngle, active.toAngle, progress)
  })
  return <group ref={group} onClick={(event) => { event.stopPropagation(); onSelect() }}>
    <mesh><boxGeometry args={[2.05, .58, 1.12]} /><meshBasicMaterial color={selected ? '#ffffff' : colorForVehicle(track.vehicle.id)} /></mesh>
    <mesh position={[0, .43, 0]}><boxGeometry args={[.98, .36, .82]} /><meshBasicMaterial color={selected ? '#65edff' : '#dffeff'} /></mesh>
  </group>
}

/**
 * One instanced body and one instanced cabin per real SUMO vehicle. This keeps
 * draw calls bounded as the fleet grows; transforms interpolate only between
 * consecutive TraCI snapshots keyed by stable SUMO vehicle ID.
 */
export function VehicleFleet({ tracks, selectedVehicleId, onSelectVehicle }: VehicleFleetProps) {
  const bodyMesh = useRef<InstancedMesh>(null)
  const cabinMesh = useRef<InstancedMesh>(null)
  // Real SUMO fleets in the bundled scenario are small. Individual meshes are
  // more reliable for picking and legibility; dense production fleets retain
  // the bounded instanced path.
  const visibleTracks = tracks.length <= 128 ? tracks : tracks.filter((track) => track.vehicle.id.startsWith('demo-'))
  const visibleIds = new Set(visibleTracks.map((track) => track.vehicle.id))
  const instanceTracks = tracks.filter((track) => !visibleIds.has(track.vehicle.id))
  const tracksRef = useRef(instanceTracks)
  const animation = useRef(new Map<string, AnimatedVehicle>())
  const bodyObject = useMemo(() => new Object3D(), [])
  const cabinObject = useMemo(() => new Object3D(), [])
  const bodyColor = useMemo(() => new Color(), [])
  const cabinColor = useMemo(() => new Color(), [])

  useLayoutEffect(() => {
    tracksRef.current = instanceTracks
    const now = performance.now()
    const activeIds = new Set(instanceTracks.map((track) => track.vehicle.id))
    for (const [id] of animation.current) if (!activeIds.has(id)) animation.current.delete(id)

    for (const track of instanceTracks) {
      const id = track.vehicle.id
      const previousWorld = sumoToWorld(track.previous.x, track.previous.y)
      const targetWorld = sumoToWorld(track.vehicle.x, track.vehicle.y)
      const previousAngle = sumoAngleToWorldRotation(track.previous.angle)
      const targetAngle = sumoAngleToWorldRotation(track.vehicle.angle)
      const existing = animation.current.get(id)
      const existingProgress = existing ? Math.min(1, Math.max(0, (now - existing.startedAt) / existing.durationMs)) : 1
      const from = existing
        ? existing.from.clone().lerp(existing.to, existingProgress)
        : new Vector3(previousWorld.x, 0, previousWorld.z)
      const fromAngle = existing
        ? interpolateWorldAngle(existing.fromAngle, existing.toAngle, existingProgress)
        : previousAngle
      const simulationDelta = Math.max(0, track.snapshotTimestamp - track.previousSnapshotTimestamp)
      animation.current.set(id, {
        from,
        to: new Vector3(targetWorld.x, 0, targetWorld.z),
        fromAngle,
        toAngle: targetAngle,
        startedAt: now,
        durationMs: Math.min(750, Math.max(120, simulationDelta * 1_000)),
      })
    }

    const body = bodyMesh.current
    const cabin = cabinMesh.current
    if (!body || !cabin) return
    for (let index = 0; index < Math.min(instanceTracks.length, VEHICLE_CAPACITY); index += 1) {
      const id = instanceTracks[index].vehicle.id
      body.setColorAt(index, new Color(id === selectedVehicleId ? '#f4fbff' : colorForVehicle(id)))
      cabin.setColorAt(index, new Color(id === selectedVehicleId ? '#65edff' : '#1a4e60'))
    }
    if (body.instanceColor) body.instanceColor.needsUpdate = true
    if (cabin.instanceColor) cabin.instanceColor.needsUpdate = true
  }, [instanceTracks, selectedVehicleId])

  useFrame(() => {
    const body = bodyMesh.current
    const cabin = cabinMesh.current
    if (!body || !cabin) return
    const now = performance.now()
    const visibleCount = Math.min(tracksRef.current.length, VEHICLE_CAPACITY)
    body.count = visibleCount
    cabin.count = visibleCount
    for (let index = 0; index < visibleCount; index += 1) {
      const vehicle = animation.current.get(tracksRef.current[index].vehicle.id)
      if (!vehicle) continue
      const progress = Math.min(1, Math.max(0, (now - vehicle.startedAt) / vehicle.durationMs))
      const x = vehicle.from.x + (vehicle.to.x - vehicle.from.x) * progress
      const z = vehicle.from.z + (vehicle.to.z - vehicle.from.z) * progress
      const heading = interpolateWorldAngle(vehicle.fromAngle, vehicle.toAngle, progress)
      bodyObject.position.set(x, .42, z)
      bodyObject.rotation.set(0, heading, 0)
      bodyObject.updateMatrix()
      body.setMatrixAt(index, bodyObject.matrix)
      cabinObject.position.set(x, .93, z)
      cabinObject.rotation.set(0, heading, 0)
      cabinObject.updateMatrix()
      cabin.setMatrixAt(index, cabinObject.matrix)
      const id = tracksRef.current[index].vehicle.id
      body.setColorAt(index, bodyColor.set(id === selectedVehicleId ? '#f4fbff' : colorForVehicle(id)))
      cabin.setColorAt(index, cabinColor.set(id === selectedVehicleId ? '#65edff' : '#e6f7f7'))
    }
    body.instanceMatrix.needsUpdate = true
    cabin.instanceMatrix.needsUpdate = true
    if (body.instanceColor) body.instanceColor.needsUpdate = true
    if (cabin.instanceColor) cabin.instanceColor.needsUpdate = true
  })

  const selectInstance = (instanceId: number | undefined) => {
    const track = instanceId === undefined ? undefined : tracksRef.current[instanceId]
    if (track) onSelectVehicle(track.vehicle.id)
  }

  return <group name="real-sumo-vehicles">
    <instancedMesh ref={bodyMesh} args={[undefined, undefined, VEHICLE_CAPACITY]} frustumCulled={false} onClick={(event) => { event.stopPropagation(); selectInstance(event.instanceId) }}>
      <boxGeometry args={[1.9, .55, 1.05]} />
      <meshBasicMaterial color="#2ddced" />
    </instancedMesh>
    <instancedMesh ref={cabinMesh} args={[undefined, undefined, VEHICLE_CAPACITY]} frustumCulled={false} onClick={(event) => { event.stopPropagation(); selectInstance(event.instanceId) }}>
      <boxGeometry args={[.92, .42, .78]} />
      <meshBasicMaterial color="#e4ffff" />
    </instancedMesh>
    {visibleTracks.map((track) => <VisibleVehicleMesh key={track.vehicle.id} track={track} selected={track.vehicle.id === selectedVehicleId} onSelect={() => onSelectVehicle(track.vehicle.id)} />)}
  </group>
}
