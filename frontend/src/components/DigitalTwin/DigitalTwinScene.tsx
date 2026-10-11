import { Canvas } from '@react-three/fiber'
import type { BuildingStyle, NetworkConfig, ViewMode } from '../../types/digitalTwin'
import type { TrafficSnapshot, VehicleTrack } from '../../types/traffic'
import { sumoToWorld } from '../../data/sumoCoordinateTransform'
import { BuildingLayer } from './Building'
import { CameraController } from './CameraController'
import { CityContext } from './CityContext'
import { RoadNetwork } from './RoadNetwork'
import { TrafficLightLayer } from './TrafficLight'
import { VehicleFleet } from './Vehicle'

type SceneProps = { network: NetworkConfig; trafficByIntersection: TrafficSnapshot; vehicleTracks: VehicleTrack[]; viewMode: ViewMode; buildingStyle: BuildingStyle; selectedJunctionId: string; selectedVehicleId: string | null; followedVehicleId: string | null; onSelectJunction: (id: string) => void; onSelectVehicle: (id: string) => void; resetSignal: number; focusSignal?: number; zoomRequest?: { direction: 1 | -1; sequence: number }; showBuildings?: boolean; panMode?: boolean }

function World({ network, trafficByIntersection, vehicleTracks, viewMode, buildingStyle, selectedJunctionId, selectedVehicleId, followedVehicleId, onSelectJunction, onSelectVehicle, resetSignal, focusSignal, zoomRequest, showBuildings = true, panMode = false }: SceneProps) {
  const cameraVehicles = vehicleTracks.map(({ vehicle }) => ({ id: vehicle.id, ...sumoToWorld(vehicle.x, vehicle.y) }))
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
    <VehicleFleet tracks={vehicleTracks} selectedVehicleId={selectedVehicleId} onSelectVehicle={onSelectVehicle} />
    <CameraController mode={viewMode} selectedJunctionId={selectedJunctionId} followedVehicleId={followedVehicleId} vehicles={cameraVehicles} junctions={network.junctions} resetSignal={resetSignal} focusSignal={focusSignal} zoomRequest={zoomRequest} panMode={panMode} />
  </>
}

/** Scene composition only: static topology and dynamic traffic enter through typed props. */
export function DigitalTwinScene(props: SceneProps) {
  return <Canvas dpr={[1, 1.5]} camera={{ position: [37, 48, 43], fov: 45, near: .1, far: 300 }} gl={{ antialias: true }} shadows={false}><World {...props} /></Canvas>
}
