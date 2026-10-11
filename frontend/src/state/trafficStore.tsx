import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react'
import { CANONICAL_INTERSECTION_IDS } from '../data/urbanGridTopology'
import { getControlLoopStatus, getHealth, getIntersections, getTrafficSnapshot, getVehicleSnapshot, setControlMode as requestControlMode, stepControlLoop } from '../services/backend'
import { openTrafficSocket } from '../services/trafficSocket'
import { isSignalActuationResult } from '../types/traffic'
import type { ControlLoopStatus, ControlMode, HealthResponse, SignalActuationResult, TrafficSnapshot, TrafficState, VehicleSnapshot, VehicleTrack } from '../types/traffic'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'
export type TrafficStoreState = {
  status: ConnectionStatus
  health: HealthResponse | null
  intersectionIds: string[]
  trafficByIntersection: TrafficSnapshot
  /** Latest authoritative real SUMO fleet, keyed by stable vehicle ID. */
  vehiclesById: Record<string, VehicleTrack>
  vehicleSnapshotTimestamp: number | null
  vehicleLastReceivedAt: number | null
  /** Local revision lets reconnect REST resync avoid replacing a newer WS fleet. */
  vehicleRevision: number
  loopStatus: ControlLoopStatus | null
  latestIntervention: SignalActuationResult | null
  /** Result metadata from the last explicit live loop step, never a derived outcome. */
  lastControlCycle: { cycle: number; simulationTime: number; mode: ControlMode; actionsAttempted: number; success: boolean; errors: string[] } | null
  /** Browser receipt time in epoch milliseconds. */
  lastReceivedAt: number | null
  /** Latest SUMO simulation timestamp in seconds. */
  lastSimulationTimestamp: number | null
  lastHeartbeatAt: number | null
  error: string | null
  malformedEvents: number
  unknownEvents: number
  /** Monotonically increasing local token for a REST fallback polling session. */
  pollingGeneration: number
}

type Action =
  | { type: 'BOOTSTRAP'; health: HealthResponse; intersections: string[]; snapshot: TrafficSnapshot; vehicles: VehicleSnapshot; loopStatus: ControlLoopStatus | null }
  | { type: 'RESYNC'; health: HealthResponse; snapshot: TrafficSnapshot; vehicles: VehicleSnapshot; loopStatus: ControlLoopStatus; expectedVehicleRevision?: number }
  | { type: 'UNAVAILABLE'; error: string; health?: HealthResponse }
  | { type: 'HEALTH'; health: HealthResponse }
  | { type: 'SOCKET_OPEN' }
  | { type: 'SOCKET_CLOSE' }
  | { type: 'SOCKET_RECONNECTING' }
  | { type: 'PONG' }
  | { type: 'UPSERT'; traffic: TrafficState }
  | { type: 'VEHICLE_SNAPSHOT'; snapshot: VehicleSnapshot }
  | { type: 'POLL_SESSION_START'; generation: number }
  | { type: 'POLL_INVALIDATED'; generation: number }
  | { type: 'POLL_SUCCESS'; snapshot: TrafficSnapshot; generation: number }
  | { type: 'POLL_FAILURE'; error: string; generation: number }
  | { type: 'MALFORMED' }
  | { type: 'LOOP_STEP'; snapshot: TrafficSnapshot; mode: ControlLoopStatus['mode']; intervention: SignalActuationResult | null; cycle: number; simulationTime: number; actionsAttempted: number; success: boolean; errors: string[] }
  | { type: 'CONTROL_MODE'; mode: ControlMode }
  | { type: 'LOOP_ERROR'; error: string }

// oxlint-disable-next-line react/only-export-components
export const initialTrafficStoreState: TrafficStoreState = { status: 'connecting', health: null, intersectionIds: [], trafficByIntersection: {}, vehiclesById: {}, vehicleSnapshotTimestamp: null, vehicleLastReceivedAt: null, vehicleRevision: 0, loopStatus: null, latestIntervention: null, lastControlCycle: null, lastReceivedAt: null, lastSimulationTimestamp: null, lastHeartbeatAt: null, error: null, malformedEvents: 0, unknownEvents: 0, pollingGeneration: 0 }
const receiptNow = () => Date.now()

function latestSimulationTimestamp(snapshot: TrafficSnapshot) {
  const timestamps = Object.values(snapshot).map((traffic) => traffic.timestamp)
  return timestamps.length ? Math.max(...timestamps) : null
}

/** REST snapshots are authoritative and may legitimately reset SUMO time to zero. */
function replaceSnapshot(state: TrafficStoreState, snapshot: TrafficSnapshot) {
  const trafficByIntersection: TrafficSnapshot = {}
  let unknownEvents = state.unknownEvents
  for (const [id, traffic] of Object.entries(snapshot)) {
    if (!state.intersectionIds.includes(id) || traffic.intersection_id !== id) { unknownEvents += 1; continue }
    trafficByIntersection[id] = traffic
  }
  return { trafficByIntersection, unknownEvents, lastReceivedAt: Object.keys(trafficByIntersection).length ? receiptNow() : state.lastReceivedAt, lastSimulationTimestamp: latestSimulationTimestamp(trafficByIntersection) }
}

/** A snapshot is a full authoritative fleet: omitted IDs have left SUMO. */
function replaceVehicles(state: TrafficStoreState, snapshot: VehicleSnapshot) {
  const receivedAt = receiptNow()
  const vehiclesById: Record<string, VehicleTrack> = {}
  for (const vehicle of snapshot.vehicles) {
    vehiclesById[vehicle.id] = {
      vehicle,
      previous: state.vehiclesById[vehicle.id]?.vehicle ?? vehicle,
      previousSnapshotTimestamp: state.vehiclesById[vehicle.id]?.snapshotTimestamp ?? snapshot.timestamp,
      snapshotTimestamp: snapshot.timestamp,
      receivedAt,
    }
  }
  return { vehiclesById, vehicleSnapshotTimestamp: snapshot.timestamp, vehicleLastReceivedAt: receivedAt }
}

// oxlint-disable-next-line react/only-export-components
export function trafficStoreReducer(state: TrafficStoreState, action: Action): TrafficStoreState {
  if (action.type === 'BOOTSTRAP') {
    const canonicalIds = new Set<string>(CANONICAL_INTERSECTION_IDS)
    const ids = [...new Set(action.intersections.filter((id) => canonicalIds.has(id)))]
    const base = { ...state, health: action.health, intersectionIds: ids, loopStatus: action.loopStatus }
    const replaced = replaceSnapshot(base, action.snapshot)
    return { ...base, ...replaced, ...replaceVehicles(base, action.vehicles), status: action.health.simulation_connected ? 'connecting' : 'disconnected', lastHeartbeatAt: null, error: action.health.simulation_connected ? null : 'SUMO simulation is unavailable.' }
  }
  if (action.type === 'RESYNC') {
    const vehicleData = action.expectedVehicleRevision === undefined || action.expectedVehicleRevision === state.vehicleRevision ? replaceVehicles(state, action.vehicles) : {}
    return { ...state, ...replaceSnapshot(state, action.snapshot), ...vehicleData, health: action.health, loopStatus: action.loopStatus, error: null }
  }
  if (action.type === 'UNAVAILABLE') return { ...state, status: 'disconnected', health: action.health ?? state.health, vehiclesById: {}, vehicleSnapshotTimestamp: null, vehicleLastReceivedAt: null, lastHeartbeatAt: null, error: action.error }
  if (action.type === 'HEALTH') return { ...state, health: action.health }
  if (action.type === 'SOCKET_OPEN') return { ...state, status: 'connected', lastHeartbeatAt: receiptNow(), error: null }
  if (action.type === 'SOCKET_CLOSE') return state.status === 'disconnected' ? state : { ...state, status: 'disconnected', vehiclesById: {}, vehicleSnapshotTimestamp: null, vehicleLastReceivedAt: null, lastHeartbeatAt: null, error: 'Live traffic stream disconnected; using REST fallback.' }
  if (action.type === 'SOCKET_RECONNECTING') return { ...state, status: 'reconnecting', error: 'Reconnecting to live traffic stream.' }
  if (action.type === 'PONG') return { ...state, lastHeartbeatAt: receiptNow() }
  if (action.type === 'MALFORMED') return { ...state, malformedEvents: state.malformedEvents + 1 }
  if (action.type === 'UPSERT') {
    const id = action.traffic.intersection_id
    if (!state.intersectionIds.includes(id)) return { ...state, unknownEvents: state.unknownEvents + 1 }
    return { ...state, trafficByIntersection: { ...state.trafficByIntersection, [id]: action.traffic }, lastReceivedAt: receiptNow(), lastSimulationTimestamp: action.traffic.timestamp, lastHeartbeatAt: receiptNow(), status: 'connected', error: null }
  }
  if (action.type === 'VEHICLE_SNAPSHOT') {
    return { ...state, ...replaceVehicles(state, action.snapshot), vehicleRevision: state.vehicleRevision + 1, lastHeartbeatAt: receiptNow(), status: 'connected', error: null }
  }
  if (action.type === 'POLL_SESSION_START') return action.generation > state.pollingGeneration ? { ...state, pollingGeneration: action.generation } : state
  if (action.type === 'POLL_INVALIDATED') return action.generation > state.pollingGeneration ? { ...state, pollingGeneration: action.generation } : state
  if (action.type === 'POLL_SUCCESS') {
    if (action.generation !== state.pollingGeneration || state.status === 'connected') return state
    return { ...state, ...replaceSnapshot(state, action.snapshot), error: 'Live traffic stream disconnected; using REST fallback.' }
  }
  if (action.type === 'POLL_FAILURE') {
    if (action.generation !== state.pollingGeneration || state.status === 'connected') return state
    return { ...state, status: 'disconnected', lastHeartbeatAt: null, error: action.error }
  }
  if (action.type === 'LOOP_STEP') {
    const loopStatus = state.loopStatus ? { ...state.loopStatus, mode: action.mode } : state.loopStatus
    return { ...state, ...replaceSnapshot(state, action.snapshot), loopStatus, latestIntervention: action.intervention, lastControlCycle: { cycle: action.cycle, simulationTime: action.simulationTime, mode: action.mode, actionsAttempted: action.actionsAttempted, success: action.success, errors: action.errors }, error: null }
  }
  if (action.type === 'CONTROL_MODE') return { ...state, loopStatus: state.loopStatus ? { ...state.loopStatus, mode: action.mode } : state.loopStatus, error: null }
  if (action.type === 'LOOP_ERROR') return { ...state, error: action.error }
  return state
}

type TrafficStore = TrafficStoreState & { stepAiLoop: () => Promise<void>; setControlMode: (mode: ControlMode) => Promise<void> }
const TrafficContext = createContext<TrafficStore | null>(null)

export function TrafficProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(trafficStoreReducer, initialTrafficStoreState)
  const stateRef = useRef(initialTrafficStoreState)
  useEffect(() => { stateRef.current = state }, [state])

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let backendRetryTimer: number | null = null
    let pollTimer: number | null = null
    let reconnectAttempt = 0
    let reconnectAllowed = true
    let pollingGeneration = initialTrafficStoreState.pollingGeneration

    const invalidatePolling = () => {
      pollingGeneration += 1
      if (!disposed) dispatch({ type: 'POLL_INVALIDATED', generation: pollingGeneration })
    }

    const stopPolling = () => {
      if (pollTimer !== null) { window.clearInterval(pollTimer); pollTimer = null }
      invalidatePolling()
    }

    const scheduleBootstrap = () => {
      if (disposed || backendRetryTimer !== null) return
      reconnectAllowed = false
      backendRetryTimer = window.setTimeout(() => {
        backendRetryTimer = null
        reconnectAllowed = true
        void bootstrap()
      }, 4_000)
    }

    const pollSnapshot = async (generation: number) => {
      if (disposed || !reconnectAllowed || generation !== pollingGeneration) return
      try {
        const snapshot = await getTrafficSnapshot()
        if (disposed || !reconnectAllowed || generation !== pollingGeneration) return
        dispatch({ type: 'POLL_SUCCESS', snapshot, generation })
      } catch (error) {
        if (disposed || generation !== pollingGeneration) return
        reconnectAllowed = false
        dispatch({ type: 'POLL_FAILURE', generation, error: error instanceof Error ? error.message : 'Backend is unavailable.' })
        socket?.close()
        scheduleBootstrap()
      }
    }

    const startPolling = () => {
      if (!reconnectAllowed || pollTimer !== null) return
      const generation = ++pollingGeneration
      dispatch({ type: 'POLL_SESSION_START', generation })
      void pollSnapshot(generation)
      pollTimer = window.setInterval(() => { void pollSnapshot(generation) }, 1_000)
    }

    function scheduleReconnect() {
      if (disposed || !reconnectAllowed || reconnectTimer !== null) return
      const delay = Math.min(2_000 * 2 ** reconnectAttempt, 8_000)
      reconnectAttempt += 1
      reconnectTimer = window.setTimeout(() => { reconnectTimer = null; dispatch({ type: 'SOCKET_RECONNECTING' }); connect(true) }, delay)
    }

    function handleSocketClose() {
      if (disposed || !reconnectAllowed) return
      dispatch({ type: 'SOCKET_CLOSE' })
      startPolling()
      scheduleReconnect()
    }

    async function resyncAfterReconnect() {
      try {
        const expectedVehicleRevision = stateRef.current.vehicleRevision
        const [health, snapshot, vehicles, loopStatus] = await Promise.all([getHealth(), getTrafficSnapshot(), getVehicleSnapshot(), getControlLoopStatus()])
        if (disposed) return
        if (!health.simulation_connected) {
          reconnectAllowed = false
          dispatch({ type: 'UNAVAILABLE', health, error: 'SUMO simulation is unavailable.' })
          socket?.close()
          scheduleBootstrap()
          return
        }
        dispatch({ type: 'RESYNC', health, snapshot, vehicles, loopStatus, expectedVehicleRevision })
      } catch {
        if (!disposed) socket?.close()
      }
    }

    function connect(resyncOnOpen: boolean) {
      if (disposed || !reconnectAllowed) return
      try {
        socket = openTrafficSocket({
          onOpen: () => {
            reconnectAttempt = 0
            stopPolling()
            dispatch({ type: 'SOCKET_OPEN' })
            if (resyncOnOpen) void resyncAfterReconnect()
          },
          onUpdate: (traffic) => dispatch({ type: 'UPSERT', traffic }),
          onVehicleSnapshot: (snapshot) => dispatch({ type: 'VEHICLE_SNAPSHOT', snapshot }),
          onPong: () => dispatch({ type: 'PONG' }),
          onMalformed: () => dispatch({ type: 'MALFORMED' }),
          onError: () => undefined,
          onClose: handleSocketClose,
        })
      } catch {
        handleSocketClose()
      }
    }

    async function bootstrap() {
      try {
        const health = await getHealth()
        if (disposed) return
        if (!health.simulation_connected) {
          reconnectAllowed = false
          dispatch({ type: 'BOOTSTRAP', health, intersections: [], snapshot: {}, vehicles: { timestamp: health.simulation_time ?? 0, vehicles: [] }, loopStatus: null })
          socket?.close()
          scheduleBootstrap()
          return
        }
        reconnectAllowed = true
        const [intersections, snapshot, vehicles, loopStatus] = await Promise.all([getIntersections(), getTrafficSnapshot(), getVehicleSnapshot(), getControlLoopStatus()])
        if (disposed) return
        dispatch({ type: 'BOOTSTRAP', health, intersections, snapshot, vehicles, loopStatus })
        connect(false)
      } catch (error) {
        if (disposed) return
        reconnectAllowed = false
        dispatch({ type: 'UNAVAILABLE', error: error instanceof Error ? error.message : 'Backend is unavailable.' })
        socket?.close()
        scheduleBootstrap()
      }
    }

    const refreshHealth = async () => {
      if (disposed || !reconnectAllowed) return
      try {
        const health = await getHealth()
        if (disposed) return
        if (!health.simulation_connected) {
          reconnectAllowed = false
          dispatch({ type: 'UNAVAILABLE', health, error: 'SUMO simulation is unavailable.' })
          socket?.close()
          scheduleBootstrap()
          return
        }
        dispatch({ type: 'HEALTH', health })
      } catch (error) {
        if (disposed) return
        reconnectAllowed = false
        dispatch({ type: 'UNAVAILABLE', error: error instanceof Error ? error.message : 'Backend is unavailable.' })
        socket?.close()
        scheduleBootstrap()
      }
    }

    void bootstrap()
    const heartbeatTimer = window.setInterval(() => {
      if (disposed || !reconnectAllowed || socket?.readyState !== WebSocket.OPEN) return
      const heartbeatAge = stateRef.current.lastHeartbeatAt === null ? Number.POSITIVE_INFINITY : receiptNow() - stateRef.current.lastHeartbeatAt
      if (heartbeatAge > 8_000) { startPolling(); socket.close(); return }
      if (heartbeatAge >= 4_000) {
        try { socket.send(JSON.stringify({ action: 'ping' })) } catch { socket.close() }
      }
    }, 1_000)
    const healthTimer = window.setInterval(() => { void refreshHealth() }, 5_000)
    return () => { disposed = true; stopPolling(); window.clearInterval(heartbeatTimer); window.clearInterval(healthTimer); if (socket) socket.close(); if (reconnectTimer !== null) window.clearTimeout(reconnectTimer); if (backendRetryTimer !== null) window.clearTimeout(backendRetryTimer) }
  }, [])

  const stepAiLoop = useCallback(async () => {
    try {
      const result = await stepControlLoop()
      const intervention = result.action_results.find((action): action is Record<string, unknown> & SignalActuationResult => isSignalActuationResult(action)) ?? null
      dispatch({ type: 'LOOP_STEP', snapshot: result.states, mode: result.mode, intervention, cycle: result.cycle, simulationTime: result.simulation_time, actionsAttempted: result.actions_attempted, success: result.success, errors: result.errors })
    } catch (error) { dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to step the AI loop.' }) }
  }, [])
  const setControlMode = useCallback(async (mode: ControlMode) => {
    try {
      const response = await requestControlMode(mode)
      dispatch({ type: 'CONTROL_MODE', mode: response.mode })
    } catch (error) { dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to change the control mode.' }) }
  }, [])
  const value = useMemo<TrafficStore>(() => ({ ...state, stepAiLoop, setControlMode }), [state, stepAiLoop, setControlMode])
  return <TrafficContext.Provider value={value}>{children}</TrafficContext.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useTrafficStore() { const store = useContext(TrafficContext); if (!store) throw new Error('useTrafficStore must be used within TrafficProvider.'); return store }
