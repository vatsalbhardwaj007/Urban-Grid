import { memo, useMemo } from 'react'
import type { Junction, SignalDefinition } from '../../types/digitalTwin'
import type { SignalPhase, TrafficSnapshot } from '../../types/traffic'

const signalColors: Record<SignalPhase, string> = { RED: '#f46962', YELLOW: '#f5be59', GREEN: '#5dedb3' }
const lenses: Array<{ yOff: number; phase: SignalPhase }> = [{ yOff: .28, phase: 'RED' }, { yOff: 0, phase: 'YELLOW' }, { yOff: -.28, phase: 'GREEN' }]

/** One representative signal per monitored junction; unknown telemetry leaves all lenses dark. */
export const TrafficLight = memo(function TrafficLight({ definition, junction, phase }: { definition: SignalDefinition; junction: Junction; phase: SignalPhase | null }) {
  return <group position={[junction.x + definition.offset[0], 0, junction.z + definition.offset[1]]} rotation={[0, definition.orientation ?? 0, 0]}>
    <mesh position={[0, .95, 0]}><cylinderGeometry args={[.045, .06, 1.9, 8]} /><meshStandardMaterial color="#87979a" metalness={.4} roughness={.65} /></mesh>
    <mesh position={[0, 2.15, 0]}><boxGeometry args={[.34, 1, .27]} /><meshStandardMaterial color="#13242d" roughness={.75} /></mesh>
    {lenses.map(({ yOff, phase: lensPhase }) => <mesh key={lensPhase} position={[0, 2.15 + yOff, .145]}><sphereGeometry args={[.115, 12, 8]} /><meshBasicMaterial color={lensPhase === phase ? signalColors[lensPhase] : '#26393f'} /></mesh>)}
    {phase && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, .19, 0]}><ringGeometry args={[.18, .32, 20]} /><meshBasicMaterial color={signalColors[phase]} transparent opacity={.7} /></mesh>}
  </group>
})

export const TrafficLightLayer = memo(function TrafficLightLayer({ definitions, junctions, trafficByIntersection }: { definitions: SignalDefinition[]; junctions: Junction[]; trafficByIntersection: TrafficSnapshot }) {
  const junctionById = useMemo(() => new Map(junctions.map((junction) => [junction.id, junction])), [junctions])
  return <>{definitions.map((definition) => {
    const junction = junctionById.get(definition.junctionId)
    return junction ? <TrafficLight key={definition.id} definition={definition} junction={junction} phase={trafficByIntersection[definition.junctionId]?.signal_phase ?? null} /> : null
  })}</>
})
