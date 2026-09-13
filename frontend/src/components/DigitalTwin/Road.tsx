import { memo } from 'react'
import type { Junction, TrafficVisualStatus } from '../../types/digitalTwin'

const ROAD_HALF_W = 2.4
const KERB_W = 0.28
const SIDEWALK_W = 0.55
const ROAD_H = 0.08
const roadSurfaceColors: Record<TrafficVisualStatus, string> = { flowing: '#1d3c45', moderate: '#2e3822', critical: '#3a2120', unknown: '#182c33' }

export const Road = memo(function Road({ from, to, status }: { from: Junction; to: Junction; status: TrafficVisualStatus }) {
  const dx = to.x - from.x
  const dz = to.z - from.z
  const length = Math.hypot(dx, dz)
  const angle = -Math.atan2(dz, dx)
  const dashCount = Math.max(4, Math.floor(length / 1.6))
  const dashSpacing = length / dashCount
  return <group position={[(from.x + to.x) / 2, 0, (from.z + to.z) / 2]} rotation={[0, angle, 0]}>
    <mesh position={[0, -0.04, 0]}><boxGeometry args={[length + 1.2, 0.1, ROAD_HALF_W * 2 + KERB_W * 2 + SIDEWALK_W * 2 + 0.2]} /><meshStandardMaterial color="#0f2228" roughness={1} /></mesh>
    <mesh position={[0, 0.03, ROAD_HALF_W + KERB_W + SIDEWALK_W / 2]}><boxGeometry args={[length + 0.2, 0.06, SIDEWALK_W]} /><meshStandardMaterial color="#182e35" roughness={.95} /></mesh>
    <mesh position={[0, 0.03, -(ROAD_HALF_W + KERB_W + SIDEWALK_W / 2)]}><boxGeometry args={[length + 0.2, 0.06, SIDEWALK_W]} /><meshStandardMaterial color="#182e35" roughness={.95} /></mesh>
    <mesh position={[0, 0.06, ROAD_HALF_W + KERB_W / 2]}><boxGeometry args={[length, 0.12, KERB_W]} /><meshStandardMaterial color="#1f3f48" roughness={.85} /></mesh>
    <mesh position={[0, 0.06, -(ROAD_HALF_W + KERB_W / 2)]}><boxGeometry args={[length, 0.12, KERB_W]} /><meshStandardMaterial color="#1f3f48" roughness={.85} /></mesh>
    <mesh position={[0, ROAD_H, 0]}><boxGeometry args={[length, 0.04, ROAD_HALF_W * 2]} /><meshStandardMaterial color={roadSurfaceColors[status]} roughness={.92} metalness={.05} /></mesh>
    <mesh position={[0, ROAD_H + .021, ROAD_HALF_W - .25]}><boxGeometry args={[length, .01, .07]} /><meshBasicMaterial color="#3a6e78" transparent opacity={.75} /></mesh>
    <mesh position={[0, ROAD_H + .021, -(ROAD_HALF_W - .25)]}><boxGeometry args={[length, .01, .07]} /><meshBasicMaterial color="#3a6e78" transparent opacity={.75} /></mesh>
    {Array.from({ length: dashCount }).map((_, index) => <mesh key={index} position={[-length / 2 + dashSpacing * .5 + index * dashSpacing, ROAD_H + .022, 0]}><boxGeometry args={[dashSpacing * .45, .01, .065]} /><meshBasicMaterial color="#4a8a96" transparent opacity={.6} /></mesh>)}
    {Array.from({ length: 5 }).map((_, index) => <mesh key={`crossing-${index}`} position={[length / 2 - 1.6, ROAD_H + .022, -ROAD_HALF_W + .4 + index * ((ROAD_HALF_W * 2 - .8) / 5)]}><boxGeometry args={[.55, .01, (ROAD_HALF_W * 2 - .8) / 5 * .62]} /><meshBasicMaterial color="#2e5c66" transparent opacity={.65} /></mesh>)}
  </group>
})
