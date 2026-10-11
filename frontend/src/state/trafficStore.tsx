import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react'
import { CANONICAL_INTERSECTION_IDS } from '../data/urbanGridTopology'
import { applyManualSignalTiming as requestManualSignalTiming, BackendRequestError, getControlLoopStatus, getControlMode, getHealth, getIntersections, getTrafficSnapshot, getVehicleSnapshot, setControlMode as requestControlMode, stepControlLoop } from '../services/backend'
import { openTrafficSocket } from '../services/trafficSocket'
import { isSignalActuationResult } from '../types/traffic'
import type { ControlLoopStatus, ControlMode, HealthResponse, SignalActuationResult, TrafficSnapshot, TrafficState, VehicleSnapshot, VehicleTrack } from '../types/traffic'

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'rest-fallback' | 'telemetry-stale' | 'backend-unavailable' | 'sumo-unavailable'
export type ControlCycleSummary = { cycle: number; simulationTime: number; mode: ControlMode; actionsAttempted: number; success: boolean; errors: string[]; /** Complete, unmodified M2 result collection; not a derived recommendation. */ actionResults: Array<Record<string, unknown>> }
export type ActionHistoryRecord = { id: string; kind: 'SIGNAL' | 'ROUTE' | 'UNKNOWN'; source: string | null; target: string | null; success: boolean | null; observedAt: number; provenance: 'client-observed'; mode: ControlMode | null; details: Record<string, unknown> }
export type AnalyticsObservationSource = 'bootstrap' | 'resync' | 'websocket' | 'rest' | 'control-loop'
/** Accepted canonical observation retained only for this browser session's analytics charts. */
export type AnalyticsObservation = { intersectionId: string; simulationTime: number; receivedAt: number; source: AnalyticsObservationSource; state: TrafficState }
export type TrafficStoreState = {
  status: ConnectionStatus
  health: HealthResponse | null
  intersectionIds: string[]
  trafficByIntersection: TrafficSnapshot
  /** Latest authoritative real SUMO fleet, keyed by stable vehicle ID. */
  vehiclesById: Record<string, VehicleTrack>
  vehicleSnapshotTimestamp: number | null
  vehicleLastReceivedAt: number | null
  /** Local revision prevents delayed REST results from replacing newer telemetry. */
  vehicleRevision: number
  loopStatus: ControlLoopStatus | null
  /** The confirmed mode response is more authoritative than an older loop-status poll. */
  controlMode: ControlMode | null
  controlModeLastConfirmedAt: number | null
  modeRevision: number
  latestIntervention: SignalActuationResult | null
  lastControlCycle: ControlCycleSummary | null
  /** Bounded, browser-session-only history of complete control-loop outcomes. */
  controlCycleHistory: ControlCycleSummary[]
  actionHistory: ActionHistoryRecord[]
  analyticsHistory: AnalyticsObservation[]
  lastReceivedAt: number | null
  lastSimulationTimestamp: number | null
  lastHeartbeatAt: number | null
  error: string | null
  malformedEvents: number
  unknownEvents: number
  pollingGeneration: number
}

type Action =
  | { type: 'BOOTSTRAP'; health: HealthResponse; intersections: string[]; snapshot: TrafficSnapshot; vehicles: VehicleSnapshot; loopStatus: ControlLoopStatus | null; controlMode: ControlMode }
  | { type: 'RESYNC'; health: HealthResponse; snapshot: TrafficSnapshot; vehicles: VehicleSnapshot; loopStatus: ControlLoopStatus; controlMode: ControlMode; expectedVehicleRevision?: number; expectedModeRevision?: number }
  | { type: 'UNAVAILABLE'; error: string; status: 'backend-unavailable' | 'sumo-unavailable'; health?: HealthResponse }
  | { type: 'HEALTH'; health: HealthResponse }
  | { type: 'SOCKET_OPEN' } | { type: 'SOCKET_CLOSE' } | { type: 'SOCKET_RECONNECTING' } | { type: 'PONG' }
  | { type: 'UPSERT'; traffic: TrafficState } | { type: 'VEHICLE_SNAPSHOT'; snapshot: VehicleSnapshot }
  | { type: 'POLL_SESSION_START'; generation: number } | { type: 'POLL_INVALIDATED'; generation: number }
  | { type: 'POLL_SUCCESS'; snapshot: TrafficSnapshot; vehicles: VehicleSnapshot; generation: number } | { type: 'POLL_FAILURE'; error: string; generation: number }
  | { type: 'SIGNAL_REFRESH'; snapshot: TrafficSnapshot }
  | { type: 'ACTION_HISTORY'; records: ActionHistoryRecord[] }
  | { type: 'MALFORMED' }
  | { type: 'LOOP_STEP'; snapshot: TrafficSnapshot; mode: ControlMode; intervention: SignalActuationResult | null; cycle: ControlCycleSummary; expectedModeRevision: number }
  | { type: 'CONTROL_MODE'; mode: ControlMode } | { type: 'MODE_SYNC'; mode: ControlMode; expectedRevision: number } | { type: 'LOOP_ERROR'; error: string }

// oxlint-disable-next-line react/only-export-components
export const initialTrafficStoreState: TrafficStoreState = { status: 'connecting', health: null, intersectionIds: [], trafficByIntersection: {}, vehiclesById: {}, vehicleSnapshotTimestamp: null, vehicleLastReceivedAt: null, vehicleRevision: 0, loopStatus: null, controlMode: null, controlModeLastConfirmedAt: null, modeRevision: 0, latestIntervention: null, lastControlCycle: null, controlCycleHistory: [], actionHistory: [], analyticsHistory: [], lastReceivedAt: null, lastSimulationTimestamp: null, lastHeartbeatAt: null, error: null, malformedEvents: 0, unknownEvents: 0, pollingGeneration: 0 }
const receiptNow = () => Date.now()
const CONTROL_HISTORY_LIMIT = 12
const ACTION_HISTORY_LIMIT = 100
export const ANALYTICS_HISTORY_LIMIT = 720
let actionSequence = 0
function toActionRecord(details: Record<string, unknown>, mode: ControlMode | null): ActionHistoryRecord { const kind = 'applied_route' in details ? 'ROUTE' : 'applied_duration' in details ? 'SIGNAL' : 'UNKNOWN'; actionSequence += 1; return { id: `client-action-${actionSequence}`, kind, source: typeof details.source === 'string' ? details.source : null, target: typeof details.target === 'string' ? details.target : null, success: typeof details.success === 'boolean' ? details.success : null, observedAt: Date.now(), provenance: 'client-observed', mode, details } }

function latestSimulationTimestamp(snapshot: TrafficSnapshot) { const timestamps = Object.values(snapshot).map((traffic) => traffic.timestamp); return timestamps.length ? Math.max(...timestamps) : null }
function isSimulationRestart(state: TrafficStoreState, health: HealthResponse) { return state.lastSimulationTimestamp !== null && health.simulation_time !== null && health.simulation_time < state.lastSimulationTimestamp }

/**
 * Records only reducer-accepted backend observations. Equal simulation timestamps
 * replace their prior entry, while older timestamps are discarded. This prevents
 * component renders and delivery retries from growing a false chart history.
 */
// oxlint-disable-next-line react/only-export-components
export function appendAnalyticsHistory(history: AnalyticsObservation[], snapshot: TrafficSnapshot, intersectionIds: string[], source: AnalyticsObservationSource, reset = false, receivedAt = receiptNow()) {
  const next = reset ? [] : [...history]
  for (const [id, state] of Object.entries(snapshot)) {
    if (!intersectionIds.includes(id) || state.intersection_id !== id) continue
    let latestIndex = -1
    for (let index = next.length - 1; index >= 0; index -= 1) if (next[index].intersectionId === id) { latestIndex = index; break }
    const latest = latestIndex >= 0 ? next[latestIndex] : null
    if (latest && state.timestamp < latest.simulationTime) continue
    const observation: AnalyticsObservation = { intersectionId: id, simulationTime: state.timestamp, receivedAt, source, state }
    if (latest && state.timestamp === latest.simulationTime) next[latestIndex] = observation
    else next.push(observation)
  }
  return next.slice(-ANALYTICS_HISTORY_LIMIT)
}

/** Reconcile each intersection by simulation seconds, accepting equal timestamps idempotently. */
function reconcileSnapshot(state: TrafficStoreState, snapshot: TrafficSnapshot, allowRestart = false) {
  const trafficByIntersection: TrafficSnapshot = allowRestart ? {} : { ...state.trafficByIntersection }
  let unknownEvents = state.unknownEvents
  let accepted = false
  for (const [id, traffic] of Object.entries(snapshot)) {
    if (!state.intersectionIds.includes(id) || traffic.intersection_id !== id) { unknownEvents += 1; continue }
    const existing = state.trafficByIntersection[id]
    if (!allowRestart && existing && traffic.timestamp < existing.timestamp) continue
    trafficByIntersection[id] = traffic
    accepted = true
  }
  return { trafficByIntersection, unknownEvents, lastReceivedAt: accepted ? receiptNow() : state.lastReceivedAt, lastSimulationTimestamp: latestSimulationTimestamp(trafficByIntersection) }
}

/** A snapshot is a full authoritative fleet: omitted IDs have left SUMO. */
function reconcileVehicles(state: TrafficStoreState, snapshot: VehicleSnapshot, allowRestart = false) {
  if (!allowRestart && state.vehicleSnapshotTimestamp !== null && snapshot.timestamp < state.vehicleSnapshotTimestamp) return {}
  const receivedAt = receiptNow()
  const vehiclesById: Record<string, VehicleTrack> = {}
  for (const vehicle of snapshot.vehicles) {
    const previous = state.vehiclesById[vehicle.id]
    vehiclesById[vehicle.id] = { vehicle, previous: previous?.vehicle ?? vehicle, previousSnapshotTimestamp: previous?.snapshotTimestamp ?? snapshot.timestamp, snapshotTimestamp: snapshot.timestamp, receivedAt }
  }
  return { vehiclesById, vehicleSnapshotTimestamp: snapshot.timestamp, vehicleLastReceivedAt: receivedAt }
}

function withConfirmedMode(state: TrafficStoreState, mode: ControlMode, incrementRevision: boolean) {
  return { controlMode: mode, controlModeLastConfirmedAt: receiptNow(), modeRevision: incrementRevision ? state.modeRevision + 1 : state.modeRevision, loopStatus: state.loopStatus ? { ...state.loopStatus, mode } : state.loopStatus }
}

// oxlint-disable-next-line react/only-export-components
export function trafficStoreReducer(state: TrafficStoreState, action: Action): TrafficStoreState {
  if (action.type === 'BOOTSTRAP') {
    const canonicalIds = new Set<string>(CANONICAL_INTERSECTION_IDS)
    const ids = [...new Set(action.intersections.filter((id) => canonicalIds.has(id)))]
    const base = { ...state, health: action.health, intersectionIds: ids, loopStatus: action.loopStatus }
    const ready = action.health.simulation_connected
    return { ...base, ...reconcileSnapshot(base, action.snapshot, true), ...reconcileVehicles(base, action.vehicles, true), ...withConfirmedMode(base, action.controlMode, true), analyticsHistory: appendAnalyticsHistory(base.analyticsHistory, action.snapshot, ids, 'bootstrap', true), status: ready ? 'connecting' : 'sumo-unavailable', lastHeartbeatAt: null, error: ready ? null : 'SUMO simulation is unavailable.' }
  }
  if (action.type === 'RESYNC') {
    const restart = isSimulationRestart(state, action.health)
    const vehicles = action.expectedVehicleRevision === undefined || action.expectedVehicleRevision === state.vehicleRevision ? reconcileVehicles(state, action.vehicles, restart) : {}
    const modeIsFresh = action.expectedModeRevision === undefined || action.expectedModeRevision === state.modeRevision
    const base = { ...state, health: action.health, loopStatus: modeIsFresh ? action.loopStatus : state.loopStatus }
    return { ...base, ...reconcileSnapshot(base, action.snapshot, restart), ...vehicles, ...(modeIsFresh ? withConfirmedMode(base, action.controlMode, true) : {}), analyticsHistory: appendAnalyticsHistory(base.analyticsHistory, action.snapshot, base.intersectionIds, 'resync', restart), error: null }
  }
  if (action.type === 'UNAVAILABLE') return { ...state, status: action.status, health: action.health ?? state.health, lastHeartbeatAt: null, error: action.error }
  if (action.type === 'HEALTH') return { ...state, health: action.health }
  if (action.type === 'SOCKET_OPEN') return { ...state, status: 'connected', lastHeartbeatAt: receiptNow(), error: null }
  if (action.type === 'SOCKET_CLOSE') return state.status === 'sumo-unavailable' || state.status === 'backend-unavailable' ? state : { ...state, status: 'telemetry-stale', lastHeartbeatAt: null, error: 'Live traffic stream disconnected; retaining the last real snapshot.' }
  if (action.type === 'SOCKET_RECONNECTING') return { ...state, status: 'reconnecting', error: 'Reconnecting to the live traffic stream.' }
  if (action.type === 'PONG') return { ...state, lastHeartbeatAt: receiptNow() }
  if (action.type === 'MALFORMED') return { ...state, malformedEvents: state.malformedEvents + 1 }
  if (action.type === 'UPSERT') {
    const id = action.traffic.intersection_id
    if (!state.intersectionIds.includes(id)) return { ...state, unknownEvents: state.unknownEvents + 1 }
    const existing = state.trafficByIntersection[id]
    if (existing && action.traffic.timestamp < existing.timestamp) return state
    const merged = reconcileSnapshot(state, { [id]: action.traffic })
    return { ...state, ...merged, analyticsHistory: appendAnalyticsHistory(state.analyticsHistory, { [id]: action.traffic }, state.intersectionIds, 'websocket'), lastHeartbeatAt: receiptNow(), status: 'connected', error: null }
  }
  if (action.type === 'VEHICLE_SNAPSHOT') {
    const vehicles = reconcileVehicles(state, action.snapshot)
    if (!Object.keys(vehicles).length) return state
    return { ...state, ...vehicles, vehicleRevision: state.vehicleRevision + 1, lastHeartbeatAt: receiptNow(), status: 'connected', error: null }
  }
  if (action.type === 'POLL_SESSION_START') return action.generation > state.pollingGeneration ? { ...state, pollingGeneration: action.generation } : state
  if (action.type === 'POLL_INVALIDATED') return action.generation > state.pollingGeneration ? { ...state, pollingGeneration: action.generation } : state
  if (action.type === 'POLL_SUCCESS') {
    if (action.generation !== state.pollingGeneration || state.status === 'connected') return state
    return { ...state, ...reconcileSnapshot(state, action.snapshot), ...reconcileVehicles(state, action.vehicles), analyticsHistory: appendAnalyticsHistory(state.analyticsHistory, action.snapshot, state.intersectionIds, 'rest'), status: 'rest-fallback', error: 'Live stream unavailable; receiving authoritative REST telemetry.' }
  }
  if (action.type === 'POLL_FAILURE') return action.generation !== state.pollingGeneration || state.status === 'connected' ? state : { ...state, status: 'backend-unavailable', lastHeartbeatAt: null, error: action.error }
  if (action.type === 'SIGNAL_REFRESH') return { ...state, ...reconcileSnapshot(state, action.snapshot), analyticsHistory: appendAnalyticsHistory(state.analyticsHistory, action.snapshot, state.intersectionIds, 'rest') }
  if (action.type === 'ACTION_HISTORY') return { ...state, actionHistory: [...action.records, ...state.actionHistory].slice(0, ACTION_HISTORY_LIMIT) }
  if (action.type === 'LOOP_STEP') {
    const history = [action.cycle, ...state.controlCycleHistory].slice(0, CONTROL_HISTORY_LIMIT)
    const modeIsFresh = action.expectedModeRevision === state.modeRevision
    const base = { ...state, loopStatus: modeIsFresh && state.loopStatus ? { ...state.loopStatus, mode: action.mode } : state.loopStatus }
    return { ...base, ...reconcileSnapshot(base, action.snapshot), ...(modeIsFresh ? withConfirmedMode(base, action.mode, true) : {}), analyticsHistory: appendAnalyticsHistory(base.analyticsHistory, action.snapshot, base.intersectionIds, 'control-loop'), actionHistory: [...action.cycle.actionResults.map((item) => toActionRecord(item, action.mode)), ...state.actionHistory].slice(0, ACTION_HISTORY_LIMIT), latestIntervention: action.intervention, lastControlCycle: action.cycle, controlCycleHistory: history, error: null }
  }
  if (action.type === 'CONTROL_MODE') return { ...state, ...withConfirmedMode(state, action.mode, true), error: null }
  if (action.type === 'MODE_SYNC') return action.expectedRevision !== state.modeRevision ? state : { ...state, ...withConfirmedMode(state, action.mode, true), error: null }
  if (action.type === 'LOOP_ERROR') return { ...state, error: action.error }
  return state
}

type TrafficStore = TrafficStoreState & { stepAiLoop: () => Promise<void>; setControlMode: (mode: ControlMode) => Promise<void>; applyManualSignalTiming: (target: string, duration: number) => Promise<SignalActuationResult> }
const TrafficContext = createContext<TrafficStore | null>(null)

export function TrafficProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(trafficStoreReducer, initialTrafficStoreState)
  const stateRef = useRef(initialTrafficStoreState)
  const modeRequestGeneration = useRef(0)
  useEffect(() => { stateRef.current = state }, [state])
  useEffect(() => {
    let disposed = false; let socket: WebSocket | null = null; let reconnectTimer: number | null = null; let backendRetryTimer: number | null = null; let pollTimer: number | null = null; let reconnectAttempt = 0; let reconnectAllowed = true; let pollInFlight = false; let pollingGeneration = initialTrafficStoreState.pollingGeneration
    const invalidatePolling = () => { pollingGeneration += 1; if (!disposed) dispatch({ type: 'POLL_INVALIDATED', generation: pollingGeneration }) }
    const stopPolling = () => { if (pollTimer !== null) { window.clearInterval(pollTimer); pollTimer = null }; invalidatePolling() }
    const scheduleBootstrap = () => { if (disposed || backendRetryTimer !== null) return; reconnectAllowed = false; backendRetryTimer = window.setTimeout(() => { backendRetryTimer = null; reconnectAllowed = true; void bootstrap() }, 4_000) }
    const pollSnapshot = async (generation: number) => {
      if (disposed || !reconnectAllowed || generation !== pollingGeneration || pollInFlight) return
      pollInFlight = true
      try { const [snapshot, vehicles] = await Promise.all([getTrafficSnapshot(), getVehicleSnapshot()]); if (!disposed && reconnectAllowed && generation === pollingGeneration) dispatch({ type: 'POLL_SUCCESS', snapshot, vehicles, generation }) }
      catch (error) { if (!disposed && generation === pollingGeneration) { reconnectAllowed = false; dispatch({ type: 'POLL_FAILURE', generation, error: error instanceof Error ? error.message : 'Backend is unavailable.' }); socket?.close(); scheduleBootstrap() } }
      finally { pollInFlight = false }
    }
    const startPolling = () => { if (!reconnectAllowed || pollTimer !== null) return; const generation = ++pollingGeneration; dispatch({ type: 'POLL_SESSION_START', generation }); void pollSnapshot(generation); pollTimer = window.setInterval(() => { void pollSnapshot(generation) }, 1_000) }
    function scheduleReconnect() { if (disposed || !reconnectAllowed || reconnectTimer !== null) return; const delay = Math.min(2_000 * 2 ** reconnectAttempt, 8_000); reconnectAttempt += 1; reconnectTimer = window.setTimeout(() => { reconnectTimer = null; dispatch({ type: 'SOCKET_RECONNECTING' }); connect(true) }, delay) }
    function handleSocketClose() { if (disposed || !reconnectAllowed) return; dispatch({ type: 'SOCKET_CLOSE' }); startPolling(); scheduleReconnect() }
    async function resyncAfterReconnect() {
      try {
        const expectedVehicleRevision = stateRef.current.vehicleRevision
        const expectedModeRevision = stateRef.current.modeRevision
        const [health, snapshot, vehicles, loopStatus, mode] = await Promise.all([getHealth(), getTrafficSnapshot(), getVehicleSnapshot(), getControlLoopStatus(), getControlMode()])
        if (disposed) return
        if (!health.simulation_connected) { reconnectAllowed = false; dispatch({ type: 'UNAVAILABLE', health, status: 'sumo-unavailable', error: 'SUMO simulation is unavailable.' }); socket?.close(); scheduleBootstrap(); return }
        dispatch({ type: 'RESYNC', health, snapshot, vehicles, loopStatus, controlMode: mode.mode, expectedVehicleRevision, expectedModeRevision })
      } catch { if (!disposed) socket?.close() }
    }
    function connect(resyncOnOpen: boolean) {
      if (disposed || !reconnectAllowed) return
      try { socket = openTrafficSocket({ onOpen: () => { reconnectAttempt = 0; stopPolling(); dispatch({ type: 'SOCKET_OPEN' }); if (resyncOnOpen) void resyncAfterReconnect() }, onUpdate: (traffic) => dispatch({ type: 'UPSERT', traffic }), onVehicleSnapshot: (snapshot) => dispatch({ type: 'VEHICLE_SNAPSHOT', snapshot }), onPong: () => dispatch({ type: 'PONG' }), onMalformed: () => dispatch({ type: 'MALFORMED' }), onError: () => undefined, onClose: handleSocketClose }) } catch { handleSocketClose() }
    }
    async function bootstrap() {
      try {
        const health = await getHealth(); if (disposed) return
        if (!health.simulation_connected) { reconnectAllowed = false; dispatch({ type: 'UNAVAILABLE', health, status: 'sumo-unavailable', error: 'SUMO simulation is unavailable.' }); socket?.close(); scheduleBootstrap(); return }
        reconnectAllowed = true
        const [intersections, snapshot, vehicles, loopStatus, mode] = await Promise.all([getIntersections(), getTrafficSnapshot(), getVehicleSnapshot(), getControlLoopStatus(), getControlMode()])
        if (disposed) return
        dispatch({ type: 'BOOTSTRAP', health, intersections, snapshot, vehicles, loopStatus, controlMode: mode.mode }); connect(false)
      } catch (error) { if (disposed) return; reconnectAllowed = false; dispatch({ type: 'UNAVAILABLE', status: 'backend-unavailable', error: error instanceof Error ? error.message : 'Backend is unavailable.' }); socket?.close(); scheduleBootstrap() }
    }
    const refreshHealth = async () => {
      if (disposed || !reconnectAllowed) return
      const expectedRevision = stateRef.current.modeRevision
      try {
        const [health, mode] = await Promise.all([getHealth(), getControlMode()]); if (disposed) return
        if (!health.simulation_connected) { reconnectAllowed = false; dispatch({ type: 'UNAVAILABLE', health, status: 'sumo-unavailable', error: 'SUMO simulation is unavailable.' }); socket?.close(); scheduleBootstrap(); return }
        dispatch({ type: 'HEALTH', health }); dispatch({ type: 'MODE_SYNC', mode: mode.mode, expectedRevision })
      } catch (error) { if (disposed) return; reconnectAllowed = false; dispatch({ type: 'UNAVAILABLE', status: 'backend-unavailable', error: error instanceof Error ? error.message : 'Backend is unavailable.' }); socket?.close(); scheduleBootstrap() }
    }
    void bootstrap()
    const heartbeatTimer = window.setInterval(() => { if (disposed || !reconnectAllowed || socket?.readyState !== WebSocket.OPEN) return; const heartbeatAge = stateRef.current.lastHeartbeatAt === null ? Number.POSITIVE_INFINITY : receiptNow() - stateRef.current.lastHeartbeatAt; if (heartbeatAge > 8_000) { startPolling(); socket.close(); return }; if (heartbeatAge >= 4_000) { try { socket.send(JSON.stringify({ action: 'ping' })) } catch { socket.close() } } }, 1_000)
    const healthTimer = window.setInterval(() => { void refreshHealth() }, 5_000)
    return () => { disposed = true; stopPolling(); window.clearInterval(heartbeatTimer); window.clearInterval(healthTimer); if (socket) socket.close(); if (reconnectTimer !== null) window.clearTimeout(reconnectTimer); if (backendRetryTimer !== null) window.clearTimeout(backendRetryTimer) }
  }, [])
  const stepAiLoop = useCallback(async () => {
    const expectedModeRevision = stateRef.current.modeRevision
    try {
      const result = await stepControlLoop()
      const intervention = result.action_results.find((action): action is Record<string, unknown> & SignalActuationResult => isSignalActuationResult(action)) ?? null
      const cycle: ControlCycleSummary = { cycle: result.cycle, simulationTime: result.simulation_time, mode: result.mode, actionsAttempted: result.actions_attempted, success: result.success, errors: result.errors, actionResults: result.action_results }
      dispatch({ type: 'LOOP_STEP', snapshot: result.states, mode: result.mode, intervention, cycle, expectedModeRevision })
    } catch (error) { dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to step the AI loop.' }) }
  }, [])
  const setControlMode = useCallback(async (mode: ControlMode) => {
    const requestGeneration = ++modeRequestGeneration.current
    try { const response = await requestControlMode(mode); if (requestGeneration === modeRequestGeneration.current) dispatch({ type: 'CONTROL_MODE', mode: response.mode }) }
    catch (error) { if (requestGeneration === modeRequestGeneration.current) dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to change the control mode.' }) }
  }, [])
  const applyManualSignalTiming = useCallback(async (target: string, duration: number) => {
    const current = stateRef.current
    if (current.health?.simulation_connected !== true || current.status === 'backend-unavailable' || current.status === 'sumo-unavailable') throw new BackendRequestError('SUMO and backend connectivity are required for manual signal control.')
    if (current.controlMode !== 'MANUAL') throw new BackendRequestError('Manual signal control is available only when the backend-confirmed mode is MANUAL.')
    if (!current.intersectionIds.includes(target)) throw new BackendRequestError('The selected intersection is not available for control.')
    let result: SignalActuationResult
    try { result = await requestManualSignalTiming({ target, green_duration: duration, source: 'MANUAL', timestamp: new Date().toISOString() }) }
    catch (error) { dispatch({ type: 'ACTION_HISTORY', records: [toActionRecord({ target, source: 'MANUAL', success: false, message: error instanceof Error ? error.message : 'Manual signal request failed.' }, current.controlMode)] }); throw error }
    dispatch({ type: 'ACTION_HISTORY', records: [toActionRecord({ ...result }, current.controlMode)] })
    const expectedModeRevision = stateRef.current.modeRevision
    const [snapshot, mode] = await Promise.allSettled([getTrafficSnapshot(), getControlMode()])
    if (snapshot.status === 'fulfilled') dispatch({ type: 'SIGNAL_REFRESH', snapshot: snapshot.value })
    if (mode.status === 'fulfilled') dispatch({ type: 'MODE_SYNC', mode: mode.value.mode, expectedRevision: expectedModeRevision })
    return result
  }, [])
  const value = useMemo<TrafficStore>(() => ({ ...state, stepAiLoop, setControlMode, applyManualSignalTiming }), [state, stepAiLoop, setControlMode, applyManualSignalTiming])
  return <TrafficContext.Provider value={value}>{children}</TrafficContext.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useTrafficStore() { const store = useContext(TrafficContext); if (!store) throw new Error('useTrafficStore must be used within TrafficProvider.'); return store }
