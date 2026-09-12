import { Canvas } from '@react-three/fiber'
import { Stars } from '@react-three/drei'
import type { BuildingStyle, NetworkConfig, ViewMode } from '../../types/digitalTwin'
import type { TrafficSnapshot } from '../../types/traffic'
import { BuildingLayer } from './Building'
import { CameraController } from './CameraController'
import { RoadNetwork } from './RoadNetwork'
import { TrafficLightLayer } from './TrafficLight'

type SceneProps = { network: NetworkConfig; trafficByIntersection: TrafficSnapshot; viewMode: ViewMode; buildingStyle: BuildingStyle; selectedJunctionId: string; followedVehicleId: string | null; onSelectJunction: (id: string) => void; resetSignal: number }

function World({ network, trafficByIntersection, viewMode, buildingStyle, selectedJunctionId, followedVehicleId, onSelectJunction, resetSignal }: SceneProps) {
  return <>
    <color attach="background" args={['#06171c']} /><fog attach="fog" args={['#06171c', 22, 68]} />
    <ambientLight intensity={.55} color="#8ecdd8" /><directionalLight position={[12, 22, 8]} intensity={1.1} color="#b0dae2" /><directionalLight position={[-10, 14, -6]} intensity={.35} color="#1a4d5c" />
    <pointLight position={[4, 14, -2]} intensity={18} color="#ff6a55" distance={22} /><pointLight position={[-8, 10, -7]} intensity={8} color="#f2b755" distance={16} /><pointLight position={[-3, 9, 5]} intensity={7} color="#50e0a0" distance={14} />
    <Stars radius={50} depth={20} count={300} factor={2} saturation={0} fade speed={.08} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow><planeGeometry args={[90, 90]} /><meshStandardMaterial color="#081c22" roughness={1} metalness={0} /></mesh><gridHelper args={[80, 40, '#0e2e36', '#0b2530']} position={[0, .002, 0]} />
    <RoadNetwork junctions={network.junctions} roads={network.roads} trafficByIntersection={trafficByIntersection} selectedJunctionId={selectedJunctionId} onSelectJunction={onSelectJunction} />
    <BuildingLayer buildings={network.buildings} style={buildingStyle} />
    <TrafficLightLayer definitions={network.signalDefinitions} junctions={network.junctions} trafficByIntersection={trafficByIntersection} />
    <CameraController mode={viewMode} selectedJunctionId={selectedJunctionId} followedVehicleId={followedVehicleId} vehicles={[]} junctions={network.junctions} resetSignal={resetSignal} />
  </>
}

/** Scene composition only: static topology and dynamic traffic enter through typed props. */
export function DigitalTwinScene(props: SceneProps) {
  return <Canvas dpr={[1, 1.5]} camera={{ position: [2, 34, 24], fov: 38 }} gl={{ antialias: true }} shadows={false}><World {...props} /></Canvas>
}
