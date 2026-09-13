import { memo } from 'react'
import type { Junction, SignalDefinition } from '../../types/digitalTwin'
import type { SignalPhase, TrafficSnapshot } from '../../types/traffic'

const signalColors: Record<SignalPhase, string> = { RED: '#ef5050', YELLOW: '#f2b755', GREEN: '#50e0a0' }
const lenses: Array<{ yOff: number; phase: SignalPhase }> = [{ yOff: .48, phase: 'RED' }, { yOff: 0, phase: 'YELLOW' }, { yOff: -.48, phase: 'GREEN' }]

export const TrafficLight = memo(function TrafficLight({ definition, junction, phase }: { definition: SignalDefinition; junction: Junction; phase: SignalPhase }) {
  return <group position={[junction.x + definition.offset[0], 0, junction.z + definition.offset[1]]} rotation={[0, definition.orientation ?? 0, 0]}>
    <mesh position={[0, .85, 0]}><boxGeometry args={[.1, 1.7, .1]} /><meshStandardMaterial color="#0d1f25" metalness={.6} roughness={.4} /></mesh>
    <mesh position={[0, 1.85, 0]}><boxGeometry args={[.22, 1.22, .22]} /><meshStandardMaterial color="#0f2530" metalness={.4} roughness={.5} /></mesh>
    {lenses.map(({ yOff, phase: lensPhase }) => { const active = lensPhase === phase; return <group key={lensPhase} position={[0, 1.85 + yOff, .12]}><mesh><sphereGeometry args={[.09, 10, 10]} /><meshBasicMaterial color={active ? signalColors[lensPhase] : '#0d2028'} /></mesh>{active && <pointLight color={signalColors[phase]} intensity={2.5} distance={5} position={[0, 0, .1]} />}</group> })}
    <mesh position={[0, 2.55, 0]}><boxGeometry args={[.08, .08, .6]} /><meshStandardMaterial color="#0d1f25" metalness={.5} roughness={.5} /></mesh>
  </group>
})

export const TrafficLightLayer = memo(function TrafficLightLayer({ definitions, junctions, trafficByIntersection }: { definitions: SignalDefinition[]; junctions: Junction[]; trafficByIntersection: TrafficSnapshot }) {
  const junctionById = new Map(junctions.map((junction) => [junction.id, junction]))
  return <>{definitions.map((definition) => { const junction = junctionById.get(definition.junctionId); const phase = trafficByIntersection[definition.junctionId]?.signal_phase; return junction && phase ? <TrafficLight key={definition.id} definition={definition} junction={junction} phase={phase} /> : null })}</>
})
