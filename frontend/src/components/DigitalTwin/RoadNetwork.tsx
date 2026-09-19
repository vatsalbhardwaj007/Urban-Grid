import { memo, useMemo } from 'react'
import type { Junction, Road as RoadDefinition } from '../../types/digitalTwin'
import type { TrafficSnapshot } from '../../types/traffic'
import { selectIntersectionVisual, selectRoadStatus } from '../../selectors/trafficVisuals'
import { IntersectionLabel } from './IntersectionLabel'
import { Junction as JunctionMesh } from './Junction'
import { Road } from './Road'

type Props = { junctions: Junction[]; roads: RoadDefinition[]; trafficByIntersection: TrafficSnapshot; selectedJunctionId: string; onSelectJunction: (id: string) => void }

/** Boundary approaches add city context without inventing monitored intersections. */
const CityApproaches = memo(function CityApproaches({ junctions }: { junctions: Junction[] }) {
  return <>{junctions.flatMap((junction) => [
    <Road key={`${junction.id}-east-west`} from={junction} to={{ x: Math.sign(junction.x) * 29, z: junction.z }} status="unknown" approach />,
    <Road key={`${junction.id}-north-south`} from={junction} to={{ x: junction.x, z: Math.sign(junction.z) * 27 }} status="unknown" approach />,
  ])}</>
})

export const RoadNetwork = memo(function RoadNetwork({ junctions, roads, trafficByIntersection, selectedJunctionId, onSelectJunction }: Props) {
  const junctionById = useMemo(() => new Map(junctions.map((junction) => [junction.id, junction])), [junctions])
  return <>
    <CityApproaches junctions={junctions} />
    {roads.map((road) => {
      const from = junctionById.get(road.from)
      const to = junctionById.get(road.to)
      return from && to ? <Road key={road.id} from={from} to={to} status={selectRoadStatus(road, trafficByIntersection)} /> : null
    })}
    {junctions.map((junction) => {
      const traffic = trafficByIntersection[junction.id]
      const { status } = selectIntersectionVisual(traffic)
      const selected = junction.id === selectedJunctionId
      return <group key={junction.id}>
        <JunctionMesh junction={junction} status={status} totalQueue={traffic?.total_queue ?? 0} selected={selected} onSelect={onSelectJunction} />
        <IntersectionLabel junction={junction} status={status} phase={traffic?.signal_phase} selected={selected} onSelect={onSelectJunction} />
      </group>
    })}
  </>
})
