import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react'
import { getControlLoopStatus, getHealth, getIntersections, getTrafficSnapshot, stepControlLoop } from '../services/backend'
import { openTrafficSocket } from '../services/trafficSocket'
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
  error: string | null
  malformedEvents: number
  unknownEvents: number
}

type Action =
  | { type: 'BOOTSTRAP'; health: HealthResponse; intersections: string[]; snapshot: TrafficSnapshot; loopStatus: ControlLoopStatus }
  | { type: 'UNAVAILABLE'; error: string }
  | { type: 'SOCKET_OPEN' }
  | { type: 'SOCKET_CLOSE' }
  | { type: 'UPSERT'; traffic: TrafficState }
  | { type: 'POLL_SUCCESS'; snapshot: TrafficSnapshot }
  | { type: 'POLL_FAILURE'; error: string }
  | { type: 'MALFORMED' }
  | { type: 'TICK' }
  | { type: 'LOOP_STEP'; snapshot: TrafficSnapshot; intervention: SignalActuationResult | null }
  | { type: 'LOOP_ERROR'; error: string }

const initialState: StoreState = { status: 'booting', health: null, intersectionIds: [], trafficByIntersection: {}, loopStatus: null, latestIntervention: null, lastReceivedAt: null, error: null, malformedEvents: 0, unknownEvents: 0 }
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
  if (action.type === 'BOOTSTRAP') return { ...state, status: action.health.simulation_connected ? 'reconnecting' : 'unavailable', health: action.health, intersectionIds: action.intersections, trafficByIntersection: action.snapshot, loopStatus: action.loopStatus, lastReceivedAt: receiptNow(), error: action.health.simulation_connected ? null : 'SUMO simulation is unavailable.' }
  if (action.type === 'UNAVAILABLE') return { ...state, status: 'unavailable', error: action.error }
  if (action.type === 'SOCKET_OPEN') return { ...state, status: 'live', error: state.health?.simulation_connected ? null : state.error, lastReceivedAt: state.lastReceivedAt ?? receiptNow() }
  if (action.type === 'SOCKET_CLOSE') return state.status === 'unavailable' ? state : { ...state, status: 'polling', error: 'Live traffic stream disconnected; using REST fallback.' }
  if (action.type === 'MALFORMED') return { ...state, malformedEvents: state.malformedEvents + 1 }
  if (action.type === 'UPSERT') {
    const id = action.traffic.intersection_id
    if (!state.intersectionIds.includes(id)) return { ...state, unknownEvents: state.unknownEvents + 1 }
    const current = state.trafficByIntersection[id]
    if (current && action.traffic.timestamp < current.timestamp) return state
    return { ...state, trafficByIntersection: { ...state.trafficByIntersection, [id]: action.traffic }, lastReceivedAt: receiptNow(), status: 'live', error: null }
  }
  if (action.type === 'POLL_SUCCESS') { const merged = mergeSnapshot(state, action.snapshot); return { ...state, ...merged, status: state.status === 'live' ? 'live' : 'polling', lastReceivedAt: receiptNow(), error: state.status === 'live' ? null : 'Live traffic stream disconnected; using REST fallback.' } }
  if (action.type === 'POLL_FAILURE') return { ...state, status: 'unavailable', error: action.error }
  if (action.type === 'TICK') return state.lastReceivedAt && receiptNow() - state.lastReceivedAt > 5_000 && state.status === 'live' ? { ...state, status: 'stale', error: 'Traffic data is stale.' } : state
  if (action.type === 'LOOP_STEP') { const merged = mergeSnapshot(state, action.snapshot); return { ...state, ...merged, latestIntervention: action.intervention, lastReceivedAt: receiptNow(), error: null } }
  if (action.type === 'LOOP_ERROR') return { ...state, error: action.error }
  return state
}

type TrafficStore = StoreState & { stepAiLoop: () => Promise<void> }
const TrafficContext = createContext<TrafficStore | null>(null)

export function TrafficProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const stateRef = useRef(state)
  stateRef.current = state

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let backendRetryTimer: number | null = null
    let pollTimer: number | null = null
    let reconnectAttempt = 0
    const stopPolling = () => { if (pollTimer !== null) { window.clearInterval(pollTimer); pollTimer = null } }
    const pollSnapshot = async () => { try { dispatch({ type: 'POLL_SUCCESS', snapshot: await getTrafficSnapshot() }) } catch (error) { dispatch({ type: 'POLL_FAILURE', error: error instanceof Error ? error.message : 'Backend is unavailable.' }) } }
    const startPolling = () => { if (pollTimer === null) { void pollSnapshot(); pollTimer = window.setInterval(() => { void pollSnapshot() }, 1_000) } }
    const connect = () => {
      if (disposed || !stateRef.current.health?.simulation_connected) return
      socket = openTrafficSocket({
        onOpen: () => { reconnectAttempt = 0; stopPolling(); dispatch({ type: 'SOCKET_OPEN' }) },
        onUpdate: (traffic) => dispatch({ type: 'UPSERT', traffic }),
        onPong: () => undefined,
        onMalformed: () => dispatch({ type: 'MALFORMED' }),
        onError: () => undefined,
        onClose: () => {
          if (disposed) return
          dispatch({ type: 'SOCKET_CLOSE' }); startPolling()
          const delay = Math.min(2_000 * 2 ** reconnectAttempt, 8_000)
          reconnectAttempt += 1
          reconnectTimer = window.setTimeout(connect, delay)
        },
      })
    }
    const bootstrap = async () => {
      try {
        const health = await getHealth()
        if (!health.simulation_connected) { dispatch({ type: 'BOOTSTRAP', health, intersections: [], snapshot: {}, loopStatus: { is_running: false, current_cycle: 0, step_interval: 0, cycle_delay: 0, error_policy: 'unavailable', decision_engine: 'unavailable' } }); return }
        const [intersections, snapshot, loopStatus] = await Promise.all([getIntersections(), getTrafficSnapshot(), getControlLoopStatus()])
        if (disposed) return
        dispatch({ type: 'BOOTSTRAP', health, intersections, snapshot, loopStatus })
        connect()
      } catch (error) {
        if (disposed) return
        dispatch({ type: 'UNAVAILABLE', error: error instanceof Error ? error.message : 'Backend is unavailable.' })
        backendRetryTimer = window.setTimeout(bootstrap, 4_000)
      }
    }
    void bootstrap()
    const staleTimer = window.setInterval(() => dispatch({ type: 'TICK' }), 1_000)
    return () => { disposed = true; stopPolling(); window.clearInterval(staleTimer); if (socket) socket.close(); if (reconnectTimer !== null) window.clearTimeout(reconnectTimer); if (backendRetryTimer !== null) window.clearTimeout(backendRetryTimer) }
  }, [])

  const stepAiLoop = useCallback(async () => {
    try {
      const result = await stepControlLoop()
      dispatch({ type: 'LOOP_STEP', snapshot: result.states, intervention: result.action_results[0] ?? null })
    } catch (error) { dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to step the AI loop.' }) }
  }, [])
  const value = useMemo<TrafficStore>(() => ({ ...state, stepAiLoop }), [state, stepAiLoop])
  return <TrafficContext.Provider value={value}>{children}</TrafficContext.Provider>
}

export function useTrafficStore() { const store = useContext(TrafficContext); if (!store) throw new Error('useTrafficStore must be used within TrafficProvider.'); return store }
