import { memo, useEffect, useMemo } from 'react'
import { BoxGeometry, EdgesGeometry, LineSegments, MeshBasicMaterial } from 'three'
import type { Building as BuildingDefinition, BuildingStyle } from '../../types/digitalTwin'

function BuildingEdges({ width, height, depth }: Pick<BuildingDefinition, 'width' | 'height' | 'depth'>) {
  const line = useMemo(() => {
    const box = new BoxGeometry(width, height, depth)
    const geometry = new EdgesGeometry(box)
    box.dispose()
    return new LineSegments(geometry, new MeshBasicMaterial({ color: '#4dd9e8', transparent: true, opacity: .75 }))
  }, [width, height, depth])
  useEffect(() => () => { line.geometry.dispose(); (line.material as MeshBasicMaterial).dispose() }, [line])
  return <primitive object={line} dispose={null} />
}

export const Building = memo(function Building({ building, style }: { building: BuildingDefinition; style: BuildingStyle }) {
  const { variant, width, height, depth, x, z } = building
  const bodyColor = variant === 'tower' ? '#162e38' : variant === 'midrise' ? '#172c34' : variant === 'commercial' ? '#1a2e35' : '#182b33'
  const wireframe = style === 'wireframe'
  const floorCount = Math.floor(height / 1.4)
  return <group position={[x, height / 2, z]}>
    <mesh castShadow><boxGeometry args={[width, height, depth]} /><meshStandardMaterial color={bodyColor} metalness={wireframe ? .6 : .35} roughness={wireframe ? .3 : .68} transparent opacity={wireframe ? .28 : 1} /></mesh>
    {wireframe && <BuildingEdges width={width} height={height} depth={depth} />}
    {wireframe && Array.from({ length: floorCount }).map((_, index) => <mesh key={index} position={[0, -height / 2 + 1.4 * (index + 1), 0]}><boxGeometry args={[width + .02, .02, depth + .02]} /><meshBasicMaterial color="#1e8a9a" transparent opacity={.4} /></mesh>)}
    {!wireframe && <>
      <mesh position={[0, height / 2 + .045, 0]}><boxGeometry args={[width + .18, .09, depth + .18]} /><meshBasicMaterial color="#2c6e78" /></mesh>
      {variant === 'tower' && <>{[-width * .25, 0, width * .25].map((wx, index) => <mesh key={index} position={[wx, 0, depth / 2 + .01]}><boxGeometry args={[width * .18, height * .78, .02]} /><meshBasicMaterial color="#2a8f9e" transparent opacity={.22} /></mesh>)}<mesh position={[0, height / 2 + .6, 0]}><boxGeometry args={[.08, 1.2, .08]} /><meshBasicMaterial color="#2a5a63" /></mesh></>}
      {variant === 'midrise' && Array.from({ length: Math.floor(height / 1.2) }).map((_, index) => <mesh key={index} position={[0, -height / 2 + .8 + index * 1.2, depth / 2 + .01]}><boxGeometry args={[width * .8, .28, .02]} /><meshBasicMaterial color="#34a8ba" transparent opacity={.18} /></mesh>)}
      {variant === 'commercial' && <mesh position={[0, -height / 2 + .5, depth / 2 + .3]}><boxGeometry args={[width + .4, .12, .6]} /><meshBasicMaterial color="#1e5a65" /></mesh>}
      {variant === 'corner' && <mesh position={[width * .22, .05, depth * .22]} rotation={[0, Math.PI / 4, 0]}><boxGeometry args={[width * .55, height + .1, depth * .55]} /><meshStandardMaterial color="#131f28" metalness={.4} roughness={.7} transparent opacity={.65} /></mesh>}
    </>}
    <mesh position={[0, height * .1, depth / 2 + .012]}><planeGeometry args={[width * .68, height * .58]} /><meshBasicMaterial color="#3dd8e8" transparent opacity={wireframe ? .06 : .09} /></mesh>
  </group>
})

export const BuildingLayer = memo(function BuildingLayer({ buildings, style }: { buildings: BuildingDefinition[]; style: BuildingStyle }) {
  return <>{buildings.map((building) => <Building key={building.id} building={building} style={style} />)}</>
})
