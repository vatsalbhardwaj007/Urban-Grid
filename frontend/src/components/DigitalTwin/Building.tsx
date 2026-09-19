import { memo, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { BoxGeometry, Color, EdgesGeometry, InstancedMesh, LineBasicMaterial, LineSegments, Object3D } from 'three'
import type { Building as BuildingDefinition, BuildingStyle } from '../../types/digitalTwin'

function BuildingEdges({ width, height, depth }: Pick<BuildingDefinition, 'width' | 'height' | 'depth'>) {
  const line = useMemo(() => {
    const box = new BoxGeometry(width, height, depth)
    const geometry = new EdgesGeometry(box)
    box.dispose()
    return new LineSegments(geometry, new LineBasicMaterial({ color: '#67b7c5', transparent: true, opacity: .7 }))
  }, [width, height, depth])
  useEffect(() => () => { line.geometry.dispose(); line.material.dispose() }, [line])
  return <primitive object={line} dispose={null} />
}

const Windows = memo(function Windows({ width, height, depth }: Pick<BuildingDefinition, 'width' | 'height' | 'depth'>) {
  const mesh = useRef<InstancedMesh>(null)
  const rows = Math.max(2, Math.floor(height / .8))
  const columns = 4
  const count = rows * columns * 4
  useLayoutEffect(() => {
    const object = new Object3D()
    const color = new Color()
    for (let side = 0; side < 4; side += 1) {
      const span = side % 2 ? depth : width
      const edge = side % 2 ? width : depth
      const angle = side * Math.PI / 2
      for (let row = 0; row < rows; row += 1) {
        for (let column = 0; column < columns; column += 1) {
          const localX = (-.36 + column * .24) * span
          const index = side * rows * columns + row * columns + column
          object.position.set(Math.cos(angle) * localX + Math.sin(angle) * (edge / 2 + .012), -height / 2 + .6 + row * (height - .95) / rows, -Math.sin(angle) * localX + Math.cos(angle) * (edge / 2 + .012))
          object.rotation.y = angle
          object.scale.set(span * .13, .37, .025)
          object.updateMatrix()
          mesh.current?.setMatrixAt(index, object.matrix)
          mesh.current?.setColorAt(index, color.set(index % 11 === 0 ? '#8b9b8d' : index % 4 === 0 ? '#375763' : '#1b303a'))
        }
      }
    }
    if (mesh.current) {
      mesh.current.instanceMatrix.needsUpdate = true
      if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true
    }
  }, [width, height, depth, rows])
  return <instancedMesh ref={mesh} args={[undefined, undefined, count]}><boxGeometry args={[1, 1, 1]} /><meshStandardMaterial roughness={.6} metalness={.15} /></instancedMesh>
})

export const Building = memo(function Building({ building, style }: { building: BuildingDefinition; style: BuildingStyle }) {
  const { variant, width, height, depth, x, z } = building
  const bodyColor = variant === 'tower' ? '#435561' : variant === 'midrise' ? '#4b6068' : variant === 'commercial' ? '#586968' : '#526167'
  const wireframe = style === 'wireframe'
  return <group position={[x, height / 2 + .12, z]}>
    <mesh><boxGeometry args={[width, height, depth]} /><meshStandardMaterial color={bodyColor} roughness={.88} metalness={.08} transparent={wireframe} opacity={wireframe ? .18 : 1} /></mesh>
    {wireframe ? <BuildingEdges width={width} height={height} depth={depth} /> : <>
      <Windows width={width} height={height} depth={depth} />
      <mesh position={[0, height / 2 + .06, 0]}><boxGeometry args={[width + .13, .12, depth + .13]} /><meshStandardMaterial color="#7c8788" roughness={1} /></mesh>
      <mesh position={[0, height / 2 + .13, 0]}><boxGeometry args={[width - .25, .035, depth - .25]} /><meshStandardMaterial color="#526268" roughness={1} /></mesh>
      <mesh position={[width * .16, height / 2 + .33, -depth * .12]}><boxGeometry args={[width * .33, .38, depth * .3]} /><meshStandardMaterial color="#65777c" roughness={.9} /></mesh>
    </>}
    <mesh position={[0, -height / 2 - .055, 0]}><boxGeometry args={[width + .5, .13, depth + .5]} /><meshStandardMaterial color="#435259" roughness={1} /></mesh>
  </group>
})

export const BuildingLayer = memo(function BuildingLayer({ buildings, style }: { buildings: BuildingDefinition[]; style: BuildingStyle }) {
  return <>{buildings.map((building) => <Building key={building.id} building={building} style={style} />)}</>
})
