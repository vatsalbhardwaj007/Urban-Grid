import { memo, useMemo } from 'react'
import type { Junction, Road as RoadDefinition } from '../../types/digitalTwin'
import type { TrafficSnapshot } from '../../types/traffic'
import { selectIntersectionVisual, selectRoadStatus } from '../../selectors/trafficVisuals'
import { Junction as JunctionMesh } from './Junction'
import { Road } from './Road'

type Props = { junctions: Junction[]; roads: RoadDefinition[]; trafficByIntersection: TrafficSnapshot; selectedJunctionId: string; onSelectJunction: (id: string) => void }

export const RoadNetwork = memo(function RoadNetwork({ junctions, roads, trafficByIntersection, selectedJunctionId, onSelectJunction }: Props) {
  const junctionById = useMemo(() => new Map(junctions.map((junction) => [junction.id, junction])), [junctions])
  return <>{roads.map((road) => { const from = junctionById.get(road.from); const to = junctionById.get(road.to); return from && to ? <Road key={road.id} from={from} to={to} status={selectRoadStatus(road, trafficByIntersection)} /> : null })}{junctions.map((junction) => { const traffic = trafficByIntersection[junction.id]; return <JunctionMesh key={junction.id} junction={junction} status={selectIntersectionVisual(traffic).status} totalQueue={traffic?.total_queue ?? 0} selected={junction.id === selectedJunctionId} onSelect={onSelectJunction} /> })}</>
})
