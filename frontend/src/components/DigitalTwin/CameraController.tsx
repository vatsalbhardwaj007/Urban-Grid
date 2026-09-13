import { OrbitControls } from '@react-three/drei'
import { useThree } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import type { ViewMode, VehicleState } from '../../types/digitalTwin'

type Props = { mode: ViewMode; selectedJunctionId: string; followedVehicleId: string | null; vehicles: VehicleState[]; junctions: Array<{ id: string; x: number; z: number }>; resetSignal: number }

export function CameraController({ mode, selectedJunctionId, followedVehicleId, vehicles, junctions, resetSignal }: Props) {
  const { camera } = useThree()
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null)
  const followed = followedVehicleId ? vehicles.find((vehicle) => vehicle.id === followedVehicleId) : undefined
  useEffect(() => {
    const selected = junctions.find((junction) => junction.id === selectedJunctionId)
    let cameraPosition: [number, number, number] = [2, 34, 24]
    let target: [number, number, number] = [0, 0, 0]
    if (mode === 'junction' && selected) { cameraPosition = [selected.x + 9, 14, selected.z + 9]; target = [selected.x, 0, selected.z] }
    if (mode === 'building') { cameraPosition = [2, 26, 18]; target = [0, 0, 2] }
    if (mode === 'followVehicle') {
      if (selected) { cameraPosition = [selected.x + 9, 14, selected.z + 9]; target = [selected.x, 0, selected.z] }
    }
    if (mode === 'localTwin') { cameraPosition = [8, 12, 6]; target = [4, 0, -2] }
    camera.position.set(...cameraPosition)
    controls.current?.target.set(...target)
    controls.current?.update()
  }, [camera, junctions, mode, resetSignal, selectedJunctionId])
  useEffect(() => {
    if (mode !== 'followVehicle' || !followed) return
    camera.position.set(followed.x + 4, 7, followed.z + 4)
    controls.current?.target.set(followed.x, 0, followed.z)
    controls.current?.update()
  }, [camera, followed, mode, resetSignal])
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.07} minDistance={6} maxDistance={58} maxPolarAngle={Math.PI / 2.05} target={[0, 0, 0]} />
}
