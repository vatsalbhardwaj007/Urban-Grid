import { memo } from 'react'
import type { Junction as JunctionDefinition, TrafficStatus } from '../../types/digitalTwin'

const ROAD_H = .08
const PAD_SIZE = 5.4
const statusColors: Record<TrafficStatus, string> = { flowing: '#63e1b3', moderate: '#f2b755', critical: '#f2766d' }
const statusEmissive: Record<TrafficStatus, string> = { flowing: '#0e3d2a', moderate: '#3d2e00', critical: '#3d0e0e' }

export const Junction = memo(function Junction({ junction, status, selected, onSelect }: { junction: JunctionDefinition; status: TrafficStatus; selected: boolean; onSelect: (id: string) => void }) {
  const statusColor = statusColors[status]
  const isFourWay = junction.type === 'four-way'
  const cornerOffset = PAD_SIZE / 2 - .35
  return <group position={[junction.x, 0, junction.z]} onClick={(event) => { event.stopPropagation(); onSelect(junction.id) }}>
    <mesh position={[0, ROAD_H, 0]}><boxGeometry args={[PAD_SIZE, .04, PAD_SIZE]} /><meshStandardMaterial color={selected ? '#163843' : status === 'critical' ? '#3a1e1a' : status === 'moderate' ? '#252d18' : '#192e36'} emissive={selected ? '#0e3040' : statusEmissive[status]} emissiveIntensity={selected ? .4 : .25} roughness={.88} metalness={.08} /></mesh>
    {[[0, -PAD_SIZE / 2 + .2, PAD_SIZE - .5, .14], [0, PAD_SIZE / 2 - .2, PAD_SIZE - .5, .14], [PAD_SIZE / 2 - .2, 0, .14, PAD_SIZE - .5]].map(([x, z, width, depth], index) => <mesh key={index} position={[x, ROAD_H + .022, z]}><boxGeometry args={[width, .01, depth]} /><meshBasicMaterial color={selected ? statusColor : '#2e5c66'} transparent opacity={selected ? .9 : .55} /></mesh>)}
    {isFourWay && <mesh position={[-(PAD_SIZE / 2 - .2), ROAD_H + .022, 0]}><boxGeometry args={[.14, .01, PAD_SIZE - .5]} /><meshBasicMaterial color={selected ? statusColor : '#2e5c66'} transparent opacity={selected ? .9 : .55} /></mesh>}
    {[[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sz], index) => <mesh key={index} position={[sx * cornerOffset, ROAD_H + .023, sz * cornerOffset]}><boxGeometry args={[.3, .01, .08]} /><meshBasicMaterial color="#3a7080" transparent opacity={.55} /></mesh>)}
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, ROAD_H + .03, 0]}><ringGeometry args={[PAD_SIZE / 2 - .08, PAD_SIZE / 2 + .18, isFourWay ? 4 : 3]} /><meshBasicMaterial color={selected ? statusColor : status === 'critical' ? '#f2766d' : '#2c5f6a'} transparent opacity={selected ? .75 : status === 'critical' ? .45 : .3} /></mesh>
    {selected && <pointLight color={statusColor} intensity={6} distance={9} position={[0, 2.5, 0]} />}
    <mesh position={[0, .45, 0]}><boxGeometry args={[.55, .08, .04]} /><meshBasicMaterial color={selected ? statusColor : '#2a6070'} transparent opacity={selected ? .9 : .45} /></mesh>
  </group>
})
