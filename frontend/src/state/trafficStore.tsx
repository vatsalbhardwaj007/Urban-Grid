import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react'
import { CANONICAL_INTERSECTION_IDS } from '../data/urbanGridTopology'
import { getControlLoopStatus, getHealth, getIntersections, getTrafficSnapshot, stepControlLoop } from '../services/backend'
import { openTrafficSocket } from '../services/trafficSocket'
import { isSignalActuationResult } from '../types/traffic'
import type { ControlLoopStatus, HealthResponse, SignalActuationResult, TrafficSnapshot, TrafficState } from '../types/traffic'

export type ConnectionStatus = 'booting' | 'live' | 'polling' | 'reconnecting' | 'stale' | 'unavailable'
type StoreState = {
  status: ConnectionStatus
  health: HealthResponse | null
  intersectionIds: string[]
  trafficByIntersection: TrafficSnapshot
  loopStatus: ControlLoopStatus | null
  latestIntervention: SignalActuationResult | null
  lastReceivedAt: number | null
  lastHeartbeatAt: number | null
  error: string | null
  malformedEvents: number
  unknownEvents: number
}

type Action =
  | { type: 'BOOTSTRAP'; health: HealthResponse; intersections: string[]; snapshot: TrafficSnapshot; loopStatus: ControlLoopStatus | null }
  | { type: 'UNAVAILABLE'; error: string; health?: HealthResponse }
  | { type: 'HEALTH'; health: HealthResponse }
  | { type: 'SOCKET_OPEN' }
  | { type: 'SOCKET_CLOSE' }
  | { type: 'PONG' }
  | { type: 'UPSERT'; traffic: TrafficState }
  | { type: 'POLL_SUCCESS'; snapshot: TrafficSnapshot }
  | { type: 'POLL_FAILURE'; error: string }
  | { type: 'MALFORMED' }
  | { type: 'TICK' }
  | { type: 'LOOP_STEP'; snapshot: TrafficSnapshot; intervention: SignalActuationResult | null }
  | { type: 'LOOP_ERROR'; error: string }

const initialState: StoreState = { status: 'booting', health: null, intersectionIds: [], trafficByIntersection: {}, loopStatus: null, latestIntervention: null, lastReceivedAt: null, lastHeartbeatAt: null, error: null, malformedEvents: 0, unknownEvents: 0 }
const receiptNow = () => Date.now()

function mergeSnapshot(state: StoreState, snapshot: TrafficSnapshot) {
  const trafficByIntersection = { ...state.trafficByIntersection }
  let unknownEvents = state.unknownEvents
  for (const [id, traffic] of Object.entries(snapshot)) {
    if (!state.intersectionIds.includes(id) || traffic.intersection_id !== id) { unknownEvents += 1; continue }
    const current = trafficByIntersection[id]
    if (!current || traffic.timestamp >= current.timestamp) trafficByIntersection[id] = traffic
  }
  return { trafficByIntersection, unknownEvents }
}

function reducer(state: StoreState, action: Action): StoreState {
  if (action.type === 'BOOTSTRAP') {
    const canonicalIds = new Set<string>(CANONICAL_INTERSECTION_IDS)
    const ids = [...new Set(action.intersections.filter((id) => canonicalIds.has(id)))]
    const snapshot = Object.fromEntries(Object.entries(action.snapshot).filter(([id, traffic]) => ids.includes(id) && traffic.intersection_id === id))
    const unknownEvents = (action.intersections.length - ids.length) + Object.keys(action.snapshot).length - Object.keys(snapshot).length
    return { ...state, status: action.health.simulation_connected ? 'reconnecting' : 'unavailable', health: action.health, intersectionIds: ids, trafficByIntersection: snapshot, loopStatus: action.loopStatus, lastReceivedAt: Object.keys(snapshot).length ? receiptNow() : null, lastHeartbeatAt: null, error: action.health.simulation_connected ? null : 'SUMO simulation is unavailable.', unknownEvents: state.unknownEvents + unknownEvents }
  }
  if (action.type === 'UNAVAILABLE') return { ...state, status: 'unavailable', health: action.health ?? state.health, lastHeartbeatAt: null, error: action.error }
  if (action.type === 'HEALTH') return { ...state, health: action.health }
  if (action.type === 'SOCKET_OPEN') return { ...state, status: 'reconnecting', lastHeartbeatAt: receiptNow(), error: null }
  if (action.type === 'SOCKET_CLOSE') return state.status === 'unavailable' ? state : { ...state, status: 'polling', lastHeartbeatAt: null, error: 'Live traffic stream disconnected; using REST fallback.' }
  if (action.type === 'PONG') return { ...state, lastHeartbeatAt: receiptNow() }
  if (action.type === 'MALFORMED') return { ...state, malformedEvents: state.malformedEvents + 1 }
  if (action.type === 'UPSERT') {
    const id = action.traffic.intersection_id
    if (!state.intersectionIds.includes(id)) return { ...state, unknownEvents: state.unknownEvents + 1 }
    const current = state.trafficByIntersection[id]
    if (current && action.traffic.timestamp < current.timestamp) return state
    return { ...state, trafficByIntersection: { ...state.trafficByIntersection, [id]: action.traffic }, lastReceivedAt: receiptNow(), lastHeartbeatAt: receiptNow(), status: 'live', error: null }
  }
  if (action.type === 'POLL_SUCCESS') { const merged = mergeSnapshot(state, action.snapshot); return { ...state, ...merged, status: state.status === 'live' ? 'live' : 'polling', lastReceivedAt: Object.keys(merged.trafficByIntersection).length ? receiptNow() : state.lastReceivedAt, error: state.status === 'live' ? null : 'Live traffic stream disconnected; using REST fallback.' } }
  if (action.type === 'POLL_FAILURE') return { ...state, status: 'unavailable', lastHeartbeatAt: null, error: action.error }
  if (action.type === 'TICK') {
    const streamUnresponsive = (state.status === 'live' || state.status === 'reconnecting') && state.lastHeartbeatAt !== null && receiptNow() - state.lastHeartbeatAt > 8_000
    return streamUnresponsive ? { ...state, status: 'stale', error: 'Live traffic stream is unresponsive.' } : state
  }
  if (action.type === 'LOOP_STEP') { const merged = mergeSnapshot(state, action.snapshot); return { ...state, ...merged, latestIntervention: action.intervention, lastReceivedAt: Object.keys(merged.trafficByIntersection).length ? receiptNow() : state.lastReceivedAt, error: null } }
  if (action.type === 'LOOP_ERROR') return { ...state, error: action.error }
  return state
}

type TrafficStore = StoreState & { stepAiLoop: () => Promise<void> }
const TrafficContext = createContext<TrafficStore | null>(null)

export function TrafficProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const stateRef = useRef(initialState)
  useEffect(() => { stateRef.current = state }, [state])

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let backendRetryTimer: number | null = null
    let pollTimer: number | null = null
    let reconnectAttempt = 0
    let reconnectAllowed = true

    const stopPolling = () => { if (pollTimer !== null) { window.clearInterval(pollTimer); pollTimer = null } }

    const scheduleBootstrap = () => {
      if (disposed || backendRetryTimer !== null) return
      reconnectAllowed = false
      backendRetryTimer = window.setTimeout(() => {
        backendRetryTimer = null
        reconnectAllowed = true
        void bootstrap()
      }, 4_000)
    }

    const pollSnapshot = async () => {
      if (disposed || !reconnectAllowed) return
      try {
        dispatch({ type: 'POLL_SUCCESS', snapshot: await getTrafficSnapshot() })
      } catch (error) {
        if (disposed) return
        reconnectAllowed = false
        dispatch({ type: 'POLL_FAILURE', error: error instanceof Error ? error.message : 'Backend is unavailable.' })
        socket?.close()
        scheduleBootstrap()
      }
    }

    const startPolling = () => { if (reconnectAllowed && pollTimer === null) { void pollSnapshot(); pollTimer = window.setInterval(() => { void pollSnapshot() }, 1_000) } }

    function scheduleReconnect() {
      if (disposed || !reconnectAllowed || reconnectTimer !== null) return
      const delay = Math.min(2_000 * 2 ** reconnectAttempt, 8_000)
      reconnectAttempt += 1
      reconnectTimer = window.setTimeout(() => { reconnectTimer = null; connect() }, delay)
    }

    function handleSocketClose() {
      if (disposed || !reconnectAllowed) return
      dispatch({ type: 'SOCKET_CLOSE' })
      startPolling()
      scheduleReconnect()
    }

    function connect() {
      if (disposed || !reconnectAllowed) return
      try {
        socket = openTrafficSocket({
          onOpen: () => { reconnectAttempt = 0; stopPolling(); dispatch({ type: 'SOCKET_OPEN' }) },
          onUpdate: (traffic) => dispatch({ type: 'UPSERT', traffic }),
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
          dispatch({ type: 'BOOTSTRAP', health, intersections: [], snapshot: {}, loopStatus: null })
          socket?.close()
          scheduleBootstrap()
          return
        }
        reconnectAllowed = true
        const [intersections, snapshot, loopStatus] = await Promise.all([getIntersections(), getTrafficSnapshot(), getControlLoopStatus()])
        if (disposed) return
        dispatch({ type: 'BOOTSTRAP', health, intersections, snapshot, loopStatus })
        connect()
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
    // M2 emits traffic updates only on simulation/control-loop steps, so an idle
    // simulation is not stale by itself. Ping/pong verifies transport liveness.
    const heartbeatTimer = window.setInterval(() => {
      if (disposed || !reconnectAllowed || socket?.readyState !== WebSocket.OPEN) return
      const current = stateRef.current
      const heartbeatAge = current.lastHeartbeatAt === null ? Number.POSITIVE_INFINITY : receiptNow() - current.lastHeartbeatAt
      if (heartbeatAge > 8_000) { dispatch({ type: 'TICK' }); startPolling(); socket.close(); return }
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
      dispatch({ type: 'LOOP_STEP', snapshot: result.states, intervention })
    } catch (error) { dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to step the AI loop.' }) }
  }, [])
  const value = useMemo<TrafficStore>(() => ({ ...state, stepAiLoop }), [state, stepAiLoop])
  return <TrafficContext.Provider value={value}>{children}</TrafficContext.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useTrafficStore() { const store = useContext(TrafficContext); if (!store) throw new Error('useTrafficStore must be used within TrafficProvider.'); return store }
