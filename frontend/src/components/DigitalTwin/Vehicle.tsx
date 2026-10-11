import { memo, useMemo } from 'react'
import { Color } from 'three'
import type { VehicleState } from '../../types/digitalTwin'

const knownVehicleColors: Record<string, string> = { V1: '#5ee0f3', V2: '#67e1b3', V3: '#f4bd5c', V4: '#f2776d', V5: '#61d3e4', V6: '#efa654', V7: '#67e1b3', V8: '#5ec9e6' }
const vehiclePalette = ['#5ee0f3', '#67e1b3', '#f4bd5c', '#f2776d', '#61d3e4', '#efa654']
function vehicleColor(id: string) { if (knownVehicleColors[id]) return knownVehicleColors[id]; return vehiclePalette[[...id].reduce((hash, character) => hash + character.charCodeAt(0), 0) % vehiclePalette.length] }

/** Stable-id renderer; a future interpolation layer can update this transform without changing topology. */
export const Vehicle = memo(function Vehicle({ vehicle }: { vehicle: VehicleState }) {
  const color = vehicleColor(vehicle.id)
  const emissive = useMemo(() => new Color(color), [color])
  return <group position={[vehicle.x, .22, vehicle.z]} rotation={[0, -vehicle.heading, 0]}>
    <mesh castShadow><boxGeometry args={[.92, .22, .46]} /><meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={.25} metalness={.5} roughness={.45} /></mesh>
    <mesh position={[.06, .19, 0]}><boxGeometry args={[.46, .18, .38]} /><meshStandardMaterial color="#1e5060" metalness={.55} roughness={.3} transparent opacity={.78} /></mesh>
    {([[.32, -.11, .25], [.32, -.11, -.25], [-.32, -.11, .25], [-.32, -.11, -.25]] as [number, number, number][]).map(([x, y, z], index) => <mesh key={index} position={[x, y, z]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[.1, .1, .1, 8]} /><meshStandardMaterial color="#0e1e24" roughness={.9} /></mesh>)}
    <mesh position={[-.48, .03, 0]}><boxGeometry args={[.02, .07, .32]} /><meshBasicMaterial color="#ff4444" transparent opacity={.7} /></mesh>
  </group>
})

export const VehicleLayer = memo(function VehicleLayer({ vehicles }: { vehicles: VehicleState[] }) {
  return <>{vehicles.map((vehicle) => <Vehicle key={vehicle.id} vehicle={vehicle} />)}</>
})
