import { memo, useLayoutEffect, useRef } from 'react'
import { Color, InstancedMesh, Object3D } from 'three'

const trees = [
  ...[-25.7, -13.7, 13.7, 25.7].flatMap((z) => [-26, -22, -18, -5, 0, 5, 18, 22, 26].map((x) => [x, z])),
  ...[-15.3, 15.3].flatMap((x) => [-24, -19, -14, -4, 0, 4, 14, 19, 24].map((z) => [x, z])),
  ...[-6.8, 6.8].flatMap((x) => [-4, 0, 4].map((z) => [x, z])),
]
const blocks = [-21.75, 0, 21.75].flatMap((x) => [-19.75, 0, 19.75].map((z) => ({ x, z, width: x === 0 ? 14.8 : 14.1, depth: z === 0 ? 10.8 : 14.1 })))

const StreetTrees = memo(function StreetTrees() {
  const trunks = useRef<InstancedMesh>(null)
  const crowns = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const object = new Object3D()
    const color = new Color()
    trees.forEach(([x, z], index) => {
      const size = .82 + index % 4 * .09
      object.position.set(x, .58, z)
      object.scale.set(1, 1, 1)
      object.updateMatrix()
      trunks.current?.setMatrixAt(index, object.matrix)
      object.position.set(x, 1.32 * size, z)
      object.scale.set(.65 * size, .87 * size, .65 * size)
      object.rotation.y = index * .9
      object.updateMatrix()
      crowns.current?.setMatrixAt(index, object.matrix)
      crowns.current?.setColorAt(index, color.set(index % 3 === 0 ? '#3e6650' : index % 3 === 1 ? '#315342' : '#456e58'))
    })
    for (const ref of [trunks, crowns]) {
      if (ref.current) ref.current.instanceMatrix.needsUpdate = true
    }
    if (crowns.current?.instanceColor) crowns.current.instanceColor.needsUpdate = true
  }, [])
  return <>
    <instancedMesh ref={trunks} args={[undefined, undefined, trees.length]}><cylinderGeometry args={[.07, .1, 1, 5]} /><meshStandardMaterial color="#5c6252" roughness={1} /></instancedMesh>
    <instancedMesh ref={crowns} args={[undefined, undefined, trees.length]}><icosahedronGeometry args={[1, 1]} /><meshStandardMaterial roughness={1} /></instancedMesh>
  </>
})

/** Static schematic urban context: landscaped blocks, paving and instanced trees. */
export const CityContext = memo(function CityContext() {
  return <>
    <mesh position={[0, -.37, 0]}><boxGeometry args={[60.5, .6, 56.5]} /><meshStandardMaterial color="#10292f" roughness={1} /></mesh>
    <mesh position={[0, -.055, 0]}><boxGeometry args={[60, .05, 56]} /><meshStandardMaterial color="#243b3c" roughness={1} /></mesh>
    {blocks.map(({ x, z, width, depth }) => <group key={`${x}-${z}`} position={[x, 0, z]}>
      <mesh position={[0, .01, 0]}><boxGeometry args={[width, .05, depth]} /><meshStandardMaterial color="#3c4d50" roughness={1} /></mesh>
      <mesh position={[0, .039, 0]}><boxGeometry args={[width - .9, .02, depth - .9]} /><meshStandardMaterial color="#29463d" roughness={1} /></mesh>
    </group>)}
    <StreetTrees />
  </>
})
