import { OrbitControls } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { MOUSE, PerspectiveCamera, TOUCH, Vector3 } from 'three'
import type { ViewMode } from '../../types/digitalTwin'
import { clampCameraDistance, clampPanTarget, getCameraPreset, getCityBounds, getCityPreset, MAX_POLAR_ANGLE, MIN_CAMERA_DISTANCE } from './cameraPresets'

type Props = {
  mode: ViewMode
  selectedJunctionId: string
  followedVehicleId: string | null
  vehicles: Array<{ id: string; x: number; z: number }>
  junctions: Array<{ id: string; x: number; z: number }>
  resetSignal: number
  focusSignal?: number
  panMode?: boolean
  zoomRequest?: { direction: 1 | -1; sequence: number }
}
type Transition = {
  fromPosition: Vector3; toPosition: Vector3; fromTarget: Vector3; toTarget: Vector3
  elapsed: number; duration: number; kind: 'preset' | 'zoom'
}

export function CameraController({ mode, selectedJunctionId, followedVehicleId, vehicles, junctions, resetSignal, focusSignal = 0, zoomRequest, panMode = false }: Props) {
  const { camera, size, gl } = useThree()
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null)
  const transition = useRef<Transition | null>(null)
  const reducedMotion = useRef(false)
  const manuallyMoved = useRef(false)
  const selected = junctions.find((junction) => junction.id === selectedJunctionId)
  const followed = followedVehicleId ? vehicles.find((vehicle) => vehicle.id === followedVehicleId) : undefined
  const { minX, maxX, minZ, maxZ } = getCityBounds(junctions)
  const aspect = size.width / Math.max(1, size.height)
  const fov = camera instanceof PerspectiveCamera ? camera.fov : 38
  const city = useMemo(() => getCityPreset({ minX, maxX, minZ, maxZ }, aspect, fov), [minX, maxX, minZ, maxZ, aspect, fov])
  const maximumDistance = Math.max(65, new Vector3(...city.position).distanceTo(new Vector3(...city.target)) * 1.35)

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => { reducedMotion.current = preference.matches }
    update()
    preference.addEventListener('change', update)
    return () => preference.removeEventListener('change', update)
  }, [])

  const moveTo = useCallback((position: Vector3, target: Vector3, kind: Transition['kind'], immediate = false) => {
    const orbit = controls.current
    if (!orbit) return
    // Flush any drag inertia before a preset so two animations do not compete.
    orbit.enableDamping = false
    orbit.update()
    orbit.enableDamping = true
    if (reducedMotion.current || immediate) {
      transition.current = null
      camera.position.copy(position)
      orbit.target.copy(target)
      orbit.update()
      return
    }
    transition.current = {
      fromPosition: camera.position.clone(), toPosition: position,
      fromTarget: orbit.target.clone(), toTarget: target,
      elapsed: 0, duration: kind === 'zoom' ? .22 : .8, kind,
    }
  }, [camera])

  const previousView = useRef<{ mode: ViewMode; resetSignal: number; focusSignal: number; selectedX?: number; selectedZ?: number; followedX?: number; followedZ?: number; city: typeof city } | null>(null)
  const selectedX = selected?.x
  const selectedZ = selected?.z
  const followedX = followed?.x
  const followedZ = followed?.z
  useEffect(() => {
    const previous = previousView.current
    const reset = previous !== null && previous.resetSignal !== resetSignal
    const newFocus = previous?.focusSignal !== focusSignal
    const junctionChanged = mode === 'junction' && (previous?.selectedX !== selectedX || previous?.selectedZ !== selectedZ)
    const vehicleChanged = mode === 'followVehicle' && (previous?.followedX !== followedX || previous?.followedZ !== followedZ)
    const fitResize = mode === 'city' && previous?.city !== city && !manuallyMoved.current
    previousView.current = { mode, resetSignal, focusSignal, selectedX, selectedZ, followedX, followedZ, city }
    if (previous && !reset && !newFocus && !junctionChanged && !vehicleChanged && !fitResize && previous.mode === mode) return
    manuallyMoved.current = false
    const preset = getCameraPreset(reset ? 'city' : mode, city,
      selectedX === undefined || selectedZ === undefined ? undefined : { x: selectedX, z: selectedZ },
      followedX === undefined || followedZ === undefined ? undefined : { x: followedX, z: followedZ })
    moveTo(new Vector3(...preset.position), new Vector3(...preset.target), 'preset', previous === null)
  }, [city, mode, selectedX, selectedZ, followedX, followedZ, resetSignal, focusSignal, moveTo])

  const zoomBy = useCallback((scale: number) => {
    const orbit = controls.current
    if (!orbit) return
    manuallyMoved.current = true
    const pending = transition.current?.kind === 'zoom' ? transition.current.toPosition : camera.position
    const offset = pending.clone().sub(orbit.target)
    const distance = clampCameraDistance(offset.length() * scale, maximumDistance)
    moveTo(offset.setLength(distance).add(orbit.target), orbit.target.clone(), 'zoom')
  }, [camera, maximumDistance, moveTo])

  const lastZoomSequence = useRef<number | undefined>(undefined)
  useEffect(() => {
    // Sequence zero is the UI's initial idle request, not a zoom command.
    if (!zoomRequest || zoomRequest.sequence === 0 || zoomRequest.sequence === lastZoomSequence.current) return
    lastZoomSequence.current = zoomRequest.sequence
    zoomBy(zoomRequest.direction === 1 ? .8 : 1.25)
  }, [zoomRequest, zoomBy])

  useEffect(() => {
    const canvas = gl.domElement
    const wheel = (event: WheelEvent) => {
      event.preventDefault()
      event.stopImmediatePropagation()
      const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.height : 1)
      zoomBy(Math.exp(Math.max(-.3, Math.min(.3, pixels * .0015))))
    }
    // Native OrbitControls dolly is immediate; use the same finite transition as +/-.
    canvas.addEventListener('wheel', wheel, { capture: true, passive: false })
    return () => canvas.removeEventListener('wheel', wheel, true)
  }, [gl, size.height, zoomBy])

  useFrame((_, delta) => {
    const motion = transition.current
    const orbit = controls.current
    if (!motion || !orbit) return
    motion.elapsed += Math.min(delta, .05)
    const progress = reducedMotion.current ? 1 : Math.min(1, motion.elapsed / motion.duration)
    const eased = progress * progress * (3 - 2 * progress)
    camera.position.lerpVectors(motion.fromPosition, motion.toPosition, eased)
    orbit.target.lerpVectors(motion.fromTarget, motion.toTarget, eased)
    orbit.update()
    if (progress === 1) transition.current = null
  })

  const constrainPan = useCallback(() => {
    const orbit = controls.current
    if (!orbit) return
    const bounded = clampPanTarget(orbit.target.x, orbit.target.z)
    camera.position.set(camera.position.x + bounded.x - orbit.target.x, camera.position.y, camera.position.z + bounded.z - orbit.target.z)
    orbit.target.set(bounded.x, orbit.target.y, bounded.z)
  }, [camera])

  // Attach to the canvas, not R3F's event wrapper: Html label presses must not start an orbit.
  return <OrbitControls ref={controls} domElement={gl.domElement} makeDefault enableDamping dampingFactor={.09}
    enablePan enableRotate enableZoom screenSpacePanning={false} panSpeed={.75} rotateSpeed={.65} zoomSpeed={.65}
    minDistance={MIN_CAMERA_DISTANCE} maxDistance={maximumDistance} minPolarAngle={.12} maxPolarAngle={MAX_POLAR_ANGLE}
    mouseButtons={{ LEFT: panMode ? MOUSE.PAN : MOUSE.ROTATE, MIDDLE: MOUSE.DOLLY, RIGHT: MOUSE.PAN }} touches={{ ONE: panMode ? TOUCH.PAN : TOUCH.ROTATE, TWO: TOUCH.DOLLY_PAN }}
    onStart={() => { transition.current = null; manuallyMoved.current = true }} onChange={constrainPan} />
}
