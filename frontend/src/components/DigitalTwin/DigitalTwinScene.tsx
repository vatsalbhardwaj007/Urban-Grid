import { Canvas } from '@react-three/fiber'
import type { BuildingStyle, NetworkConfig, ViewMode } from '../../types/digitalTwin'
import type { TrafficSnapshot } from '../../types/traffic'
import { BuildingLayer } from './Building'
import { CameraController } from './CameraController'
import { CityContext } from './CityContext'
import { RoadNetwork } from './RoadNetwork'
import { TrafficLightLayer } from './TrafficLight'

type SceneProps = { network: NetworkConfig; trafficByIntersection: TrafficSnapshot; viewMode: ViewMode; buildingStyle: BuildingStyle; selectedJunctionId: string; followedVehicleId: string | null; onSelectJunction: (id: string) => void; resetSignal: number; focusSignal?: number; zoomRequest?: { direction: 1 | -1; sequence: number }; showBuildings?: boolean; panMode?: boolean }

function World({ network, trafficByIntersection, viewMode, buildingStyle, selectedJunctionId, followedVehicleId, onSelectJunction, resetSignal, focusSignal, zoomRequest, showBuildings = true, panMode = false }: SceneProps) {
  return <>
    <color attach="background" args={['#091a23']} />
    <ambientLight intensity={.65} color="#b7d8df" />
    <hemisphereLight intensity={.65} color="#d9e8eb" groundColor="#294338" />
    <directionalLight position={[-18, 32, 16]} intensity={1.8} color="#d9e7e8" />
    <directionalLight position={[20, 12, -16]} intensity={.4} color="#779eb4" />
    <gridHelper args={[130, 65, '#15323c', '#102833']} position={[0, -.73, 0]} />
    <CityContext />
    <RoadNetwork junctions={network.junctions} roads={network.roads} trafficByIntersection={trafficByIntersection} selectedJunctionId={selectedJunctionId} onSelectJunction={onSelectJunction} />
    {showBuildings && <BuildingLayer buildings={network.buildings} style={buildingStyle} />}
    <TrafficLightLayer definitions={network.signalDefinitions} junctions={network.junctions} trafficByIntersection={trafficByIntersection} />
    <CameraController mode={viewMode} selectedJunctionId={selectedJunctionId} followedVehicleId={followedVehicleId} vehicles={[]} junctions={network.junctions} resetSignal={resetSignal} focusSignal={focusSignal} zoomRequest={zoomRequest} panMode={panMode} />
  </>
}

/** Scene composition only: static topology and dynamic traffic enter through typed props. */
export function DigitalTwinScene(props: SceneProps) {
  return <Canvas dpr={[1, 1.5]} camera={{ position: [37, 48, 43], fov: 45, near: .1, far: 300 }} gl={{ antialias: true }} shadows={false}><World {...props} /></Canvas>
}
