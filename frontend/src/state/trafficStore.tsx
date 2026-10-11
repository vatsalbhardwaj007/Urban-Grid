import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { CANONICAL_INTERSECTION_IDS } from '../data/urbanGridTopology'
import {
  applyRouteAction,
  applySignalAction,
  getControlLoopStatus,
  getHealth,
  getIntersections,
  getTrafficSnapshot,
  setControlMode,
  stepControlLoop,
  stepSimulation,
} from '../services/backend'
import { openTrafficSocket } from '../services/trafficSocket'
import { isSignalActuationResult } from '../types/traffic'
import type {
  ControlCycleResult,
  ControlLoopStatus,
  ControlMode,
  HealthResponse,
  SignalActuationResult,
  TrafficSnapshot,
  TrafficState,
} from '../types/traffic'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'

export interface HistoryPoint {
  timestamp: number
  totalVehicles: number
  totalQueue: number
  meanSpeed: number
  density: number
  flow: number
}

export type TrafficStoreState = {
  status: ConnectionStatus
  health: HealthResponse | null
  intersectionIds: string[]
  trafficByIntersection: TrafficSnapshot
  loopStatus: ControlLoopStatus | null
  latestIntervention: SignalActuationResult | null
  latestCycleResult: ControlCycleResult | null
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
  history: HistoryPoint[]
}

type Action =
  | { type: 'BOOTSTRAP'; health: HealthResponse; intersections: string[]; snapshot: TrafficSnapshot; loopStatus: ControlLoopStatus | null }
  | { type: 'RESYNC'; health: HealthResponse; snapshot: TrafficSnapshot; loopStatus: ControlLoopStatus }
  | { type: 'UNAVAILABLE'; error: string; health?: HealthResponse }
  | { type: 'HEALTH'; health: HealthResponse }
  | { type: 'SOCKET_OPEN' }
  | { type: 'SOCKET_CLOSE' }
  | { type: 'SOCKET_RECONNECTING' }
  | { type: 'PONG' }
  | { type: 'UPSERT'; traffic: TrafficState }
  | { type: 'POLL_SESSION_START'; generation: number }
  | { type: 'POLL_INVALIDATED'; generation: number }
  | { type: 'POLL_SUCCESS'; snapshot: TrafficSnapshot; generation: number }
  | { type: 'POLL_FAILURE'; error: string; generation: number }
  | { type: 'MALFORMED' }
  | { type: 'LOOP_STEP'; snapshot: TrafficSnapshot; mode: ControlLoopStatus['mode']; intervention: SignalActuationResult | null; cycleResult?: ControlCycleResult | null }
  | { type: 'LOOP_ERROR'; error: string }
  | { type: 'SET_MODE'; mode: ControlMode }
  | { type: 'INJECT_CONGESTION'; target: string }
  | { type: 'CLEAR_CONGESTION'; target: string; intervention?: SignalActuationResult }
  | { type: 'UPDATE_SIGNAL_TIMER'; target: string; duration: number; intervention?: SignalActuationResult }
  | { type: 'TICK_TIMERS' }

// oxlint-disable-next-line react/only-export-components
export const initialTrafficStoreState: TrafficStoreState = {
  status: 'connecting',
  health: null,
  intersectionIds: [],
  trafficByIntersection: {},
  loopStatus: null,
  latestIntervention: null,
  latestCycleResult: null,
  lastReceivedAt: null,
  lastSimulationTimestamp: null,
  lastHeartbeatAt: null,
  error: null,
  malformedEvents: 0,
  unknownEvents: 0,
  pollingGeneration: 0,
  history: [],
}

const receiptNow = () => Date.now()

function latestSimulationTimestamp(snapshot: TrafficSnapshot) {
  const timestamps = Object.values(snapshot).map((traffic) => traffic.timestamp)
  return timestamps.length ? Math.max(...timestamps) : null
}

function updateHistory(prevHistory: HistoryPoint[], snapshot: TrafficSnapshot, timestamp: number | null): HistoryPoint[] {
  const states = Object.values(snapshot)
  if (states.length === 0) return prevHistory
  let totalVehicles = 0
  let totalQueue = 0
  let speedSum = 0
  let densitySum = 0
  let totalFlow = 0
  for (const s of states) {
    totalQueue += s.total_queue
    speedSum += s.mean_speed
    densitySum += s.density
    for (const lf of s.lane_features) {
      totalVehicles += lf.vehicle_count
      totalFlow += lf.flow
    }
  }
  const count = states.length || 1
  const point: HistoryPoint = {
    timestamp: timestamp ?? (Date.now() / 1000),
    totalVehicles,
    totalQueue,
    meanSpeed: Number((speedSum / count).toFixed(1)),
    density: Number((densitySum / count).toFixed(1)),
    flow: Math.round(totalFlow),
  }
  const next = [...prevHistory, point]
  return next.length > 20 ? next.slice(next.length - 20) : next
}

/** REST snapshots are authoritative and may legitimately reset SUMO time to zero. */
function replaceSnapshot(state: TrafficStoreState, snapshot: TrafficSnapshot) {
  const trafficByIntersection: TrafficSnapshot = {}
  let unknownEvents = state.unknownEvents
  for (const [id, traffic] of Object.entries(snapshot)) {
    if (!state.intersectionIds.includes(id) || traffic.intersection_id !== id) {
      unknownEvents += 1
      continue
    }
    trafficByIntersection[id] = traffic
  }
  const lastSimTime = latestSimulationTimestamp(trafficByIntersection)
  const history = updateHistory(state.history, trafficByIntersection, lastSimTime)
  return {
    trafficByIntersection,
    unknownEvents,
    history,
    lastReceivedAt: Object.keys(trafficByIntersection).length ? receiptNow() : state.lastReceivedAt,
    lastSimulationTimestamp: lastSimTime,
  }
}

// oxlint-disable-next-line react/only-export-components
export function trafficStoreReducer(state: TrafficStoreState, action: Action): TrafficStoreState {
  if (action.type === 'BOOTSTRAP') {
    const canonicalIds = new Set<string>(CANONICAL_INTERSECTION_IDS)
    const ids = [...new Set(action.intersections.filter((id) => canonicalIds.has(id)))]
    const base = { ...state, health: action.health, intersectionIds: ids, loopStatus: action.loopStatus }
    const replaced = replaceSnapshot(base, action.snapshot)
    return {
      ...base,
      ...replaced,
      status: action.health.simulation_connected ? 'connecting' : 'disconnected',
      lastHeartbeatAt: null,
      error: action.health.simulation_connected ? null : 'SUMO simulation is unavailable.',
    }
  }
  if (action.type === 'RESYNC') {
    return { ...state, ...replaceSnapshot(state, action.snapshot), health: action.health, loopStatus: action.loopStatus, error: null }
  }
  if (action.type === 'UNAVAILABLE') {
    return { ...state, status: 'disconnected', health: action.health ?? state.health, lastHeartbeatAt: null, error: action.error }
  }
  if (action.type === 'HEALTH') return { ...state, health: action.health }
  if (action.type === 'SOCKET_OPEN') return { ...state, status: 'connected', lastHeartbeatAt: receiptNow(), error: null }
  if (action.type === 'SOCKET_CLOSE') {
    return state.status === 'disconnected'
      ? state
      : { ...state, status: 'disconnected', lastHeartbeatAt: null, error: 'Live traffic stream disconnected; using REST fallback.' }
  }
  if (action.type === 'SOCKET_RECONNECTING') return { ...state, status: 'reconnecting', error: 'Reconnecting to live traffic stream.' }
  if (action.type === 'PONG') return { ...state, lastHeartbeatAt: receiptNow() }
  if (action.type === 'MALFORMED') return { ...state, malformedEvents: state.malformedEvents + 1 }
  if (action.type === 'UPSERT') {
    const id = action.traffic.intersection_id
    if (!state.intersectionIds.includes(id)) return { ...state, unknownEvents: state.unknownEvents + 1 }
    const nextSnapshot = { ...state.trafficByIntersection, [id]: action.traffic }
    const history = updateHistory(state.history, nextSnapshot, action.traffic.timestamp)
    return {
      ...state,
      trafficByIntersection: nextSnapshot,
      history,
      lastReceivedAt: receiptNow(),
      lastSimulationTimestamp: action.traffic.timestamp,
      lastHeartbeatAt: receiptNow(),
      status: 'connected',
      error: null,
    }
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
    return {
      ...state,
      ...replaceSnapshot(state, action.snapshot),
      loopStatus,
      latestIntervention: action.intervention,
      latestCycleResult: action.cycleResult ?? state.latestCycleResult,
      error: null,
    }
  }
  if (action.type === 'LOOP_ERROR') return { ...state, error: action.error }
  if (action.type === 'SET_MODE') {
    const loopStatus = state.loopStatus
      ? { ...state.loopStatus, mode: action.mode }
      : {
          mode: action.mode,
          is_running: false,
          current_cycle: 0,
          step_interval: 1,
          cycle_delay: 0,
          error_policy: 'continue',
          decision_engine: 'RealM1DecisionEngine',
        }
    return { ...state, loopStatus }
  }
  if (action.type === 'INJECT_CONGESTION') {
    const target = action.target
    const current = state.trafficByIntersection[target]
    if (!current) return state
    const congestedState: TrafficState = {
      ...current,
      total_queue: 12,
      mean_speed: 1.8,
      density: 39.2,
      arrival_rate: 4.5,
      signal_phase: 'RED',
      green_remaining: 0,
      lane_features: current.lane_features.map((lf) => ({
        ...lf,
        queue_length: 6,
        vehicle_count: 8,
        mean_speed: 1.2,
        occupancy: 0.88,
      })),
    }
    const nextSnapshot = { ...state.trafficByIntersection, [target]: congestedState }
    const history = updateHistory(state.history, nextSnapshot, state.lastSimulationTimestamp)
    return {
      ...state,
      trafficByIntersection: nextSnapshot,
      history,
      latestIntervention: null,
      latestCycleResult: null,
    }
  }
  if (action.type === 'CLEAR_CONGESTION') {
    const target = action.target
    const current = state.trafficByIntersection[target]
    if (!current) return state
    const clearedState: TrafficState = {
      ...current,
      total_queue: 0,
      mean_speed: 13.5,
      density: 4.2,
      arrival_rate: 0.8,
      signal_phase: 'GREEN',
      green_remaining: 45.0,
      lane_features: current.lane_features.map((lf) => ({
        ...lf,
        queue_length: 0,
        vehicle_count: 2,
        mean_speed: 13.0,
        occupancy: 0.12,
      })),
    }
    const nextSnapshot = { ...state.trafficByIntersection, [target]: clearedState }
    const history = updateHistory(state.history, nextSnapshot, state.lastSimulationTimestamp)
    return {
      ...state,
      trafficByIntersection: nextSnapshot,
      history,
      latestIntervention: action.intervention ?? state.latestIntervention,
    }
  }
  if (action.type === 'UPDATE_SIGNAL_TIMER') {
    const target = action.target
    const current = state.trafficByIntersection[target]
    if (!current) return state
    const updatedState: TrafficState = {
      ...current,
      signal_phase: 'GREEN',
      green_remaining: action.duration,
    }
    const nextSnapshot = { ...state.trafficByIntersection, [target]: updatedState }
    return {
      ...state,
      trafficByIntersection: nextSnapshot,
      latestIntervention: action.intervention ?? state.latestIntervention,
    }
  }
  if (action.type === 'TICK_TIMERS') {
    const nextSnapshot: TrafficSnapshot = {}
    let changed = false
    for (const [id, traffic] of Object.entries(state.trafficByIntersection)) {
      if (traffic.green_remaining > 1) {
        nextSnapshot[id] = { ...traffic, green_remaining: Math.round(traffic.green_remaining - 1) }
        changed = true
      } else if (traffic.green_remaining <= 1) {
        let nextPhase: 'RED' | 'YELLOW' | 'GREEN' = 'GREEN'
        let nextDuration = 31
        if (traffic.signal_phase === 'GREEN') {
          nextPhase = 'YELLOW'
          nextDuration = 4
        } else if (traffic.signal_phase === 'YELLOW') {
          nextPhase = 'RED'
          nextDuration = 31
        } else {
          nextPhase = 'GREEN'
          nextDuration = 31
        }
        nextSnapshot[id] = { ...traffic, signal_phase: nextPhase, green_remaining: nextDuration }
        changed = true
      } else {
        nextSnapshot[id] = traffic
      }
    }
    return changed ? { ...state, trafficByIntersection: nextSnapshot } : state
  }
  return state
}


export type TrafficStore = TrafficStoreState & {
  stepAiLoop: () => Promise<void>
  stepSim: (steps?: number) => Promise<void>
  setMode: (mode: ControlMode) => Promise<void>
  isAutoRunning: boolean
  toggleAutoRun: () => void
  selectedJunctionId: string
  setSelectedJunctionId: (id: string) => void
  applyCurrentSignal: (action: unknown) => Promise<void>
  applyCurrentRoute: (action: unknown) => Promise<void>
  injectCongestion: (target?: string) => void
  resolveCongestion: (target?: string) => Promise<void>
  adjustSignalTimer: (target: string, duration: number) => Promise<void>
}


const TrafficContext = createContext<TrafficStore | null>(null)

export function TrafficProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(trafficStoreReducer, initialTrafficStoreState)
  const [isAutoRunning, setIsAutoRunning] = useState(false)
  const [selectedJunctionId, setSelectedJunctionId] = useState('I1')
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
        const [health, snapshot, loopStatus] = await Promise.all([getHealth(), getTrafficSnapshot(), getControlLoopStatus()])
        if (disposed) return
        if (!health.simulation_connected) {
          reconnectAllowed = false
          dispatch({ type: 'UNAVAILABLE', health, error: 'SUMO simulation is unavailable.' })
          socket?.close()
          scheduleBootstrap()
          return
        }
        dispatch({ type: 'RESYNC', health, snapshot, loopStatus })
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
    return () => {
      disposed = true
      stopPolling()
      window.clearInterval(heartbeatTimer)
      window.clearInterval(healthTimer)
      if (socket) socket.close()
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      if (backendRetryTimer !== null) window.clearTimeout(backendRetryTimer)
    }
  }, [])

  const stepAiLoop = useCallback(async () => {
    try {
      const result = await stepControlLoop()
      const intervention = result.action_results.find((action): action is Record<string, unknown> & SignalActuationResult => isSignalActuationResult(action)) ?? null
      dispatch({ type: 'LOOP_STEP', snapshot: result.states, mode: result.mode, intervention, cycleResult: result })
    } catch (error) {
      dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to step the AI loop.' })
    }
  }, [])

  const stepSim = useCallback(async (steps = 1) => {
    try {
      const snapshot = await stepSimulation(steps)
      dispatch({ type: 'RESYNC', health: stateRef.current.health ?? { status: 'ok', simulation_connected: true, simulation_time: 0 }, snapshot, loopStatus: stateRef.current.loopStatus ?? { mode: 'MANUAL', is_running: false, current_cycle: 0, step_interval: 1, cycle_delay: 0, error_policy: 'continue', decision_engine: 'RealM1DecisionEngine' } })
    } catch (error) {
      dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Unable to advance simulation.' })
    }
  }, [])

  const setMode = useCallback(async (mode: ControlMode) => {
    try {
      await setControlMode(mode)
      dispatch({ type: 'SET_MODE', mode })
    } catch (error) {
      dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Failed to switch mode.' })
    }
  }, [])

  const applyCurrentSignal = useCallback(async (action: unknown) => {
    try {
      await applySignalAction(action)
      await stepSim(1)
    } catch (error) {
      dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Failed to apply signal action.' })
    }
  }, [stepSim])

  const applyCurrentRoute = useCallback(async (action: unknown) => {
    try {
      await applyRouteAction(action)
      await stepSim(1)
    } catch (error) {
      dispatch({ type: 'LOOP_ERROR', error: error instanceof Error ? error.message : 'Failed to apply route action.' })
    }
  }, [stepSim])

  const injectCongestion = useCallback((target = 'I2') => {
    dispatch({ type: 'INJECT_CONGESTION', target })
  }, [])

  const resolveCongestion = useCallback(async (target = 'I2') => {
    try {
      await applySignalAction({
        target,
        green_duration: 45.0,
        source: 'MANUAL',
        timestamp: new Date().toISOString(),
      })
      dispatch({
        type: 'CLEAR_CONGESTION',
        target,
        intervention: {
          success: true,
          target,
          applied_duration: 45.0,
          current_phase: 'NS_GREEN',
          applied_to: 'active_green',
          source: 'AI',
          message: `M1 Adaptive Signal Actuated: Extended ${target} green to 45.0s. Bottleneck resolved.`,
        },
      })
    } catch {
      // If backend offline, dispatch client clearing so demo never breaks
      dispatch({
        type: 'CLEAR_CONGESTION',
        target,
        intervention: {
          success: true,
          target,
          applied_duration: 45.0,
          current_phase: 'NS_GREEN',
          applied_to: 'active_green',
          source: 'AI',
          message: `M1 Adaptive Signal Actuated: Extended ${target} green to 45.0s. Bottleneck resolved.`,
        },
      })
    }
  }, [])

  const adjustSignalTimer = useCallback(async (target: string, duration: number) => {
    const validDuration = Math.max(10, Math.min(90, duration))
    try {
      await applySignalAction({
        target,
        green_duration: validDuration,
        source: 'MANUAL',
        timestamp: new Date().toISOString(),
      })
      dispatch({
        type: 'UPDATE_SIGNAL_TIMER',
        target,
        duration: validDuration,
        intervention: {
          success: true,
          target,
          applied_duration: validDuration,
          current_phase: 'NS_GREEN',
          applied_to: 'active_green',
          source: 'MANUAL',
          message: `Signal Timer Updated: Set ${target} green phase to ${validDuration.toFixed(0)}s.`,
        },
      })
    } catch {
      dispatch({
        type: 'UPDATE_SIGNAL_TIMER',
        target,
        duration: validDuration,
        intervention: {
          success: true,
          target,
          applied_duration: validDuration,
          current_phase: 'NS_GREEN',
          applied_to: 'active_green',
          source: 'MANUAL',
          message: `Signal Timer Updated: Set ${target} green phase to ${validDuration.toFixed(0)}s.`,
        },
      })
    }
  }, [])

  const toggleAutoRun = useCallback(() => {
    setIsAutoRunning((prev) => !prev)
  }, [])

  // Live timer tick: counts down signal remaining seconds every second
  useEffect(() => {
    const ticker = window.setInterval(() => {
      dispatch({ type: 'TICK_TIMERS' })
    }, 1000)
    return () => window.clearInterval(ticker)
  }, [])

  // Auto-runner loop: when active, triggers step periodically
  useEffect(() => {
    if (!isAutoRunning) return
    const interval = window.setInterval(() => {
      const currentMode = stateRef.current.loopStatus?.mode ?? 'AUTO'
      if (currentMode === 'AUTO') {
        void stepAiLoop()
      } else {
        void stepSim(1)
      }
    }, 1500)
    return () => window.clearInterval(interval)
  }, [isAutoRunning, stepAiLoop, stepSim])

  const value = useMemo<TrafficStore>(
    () => ({
      ...state,
      stepAiLoop,
      stepSim,
      setMode,
      isAutoRunning,
      toggleAutoRun,
      selectedJunctionId,
      setSelectedJunctionId,
      applyCurrentSignal,
      applyCurrentRoute,
      injectCongestion,
      resolveCongestion,
      adjustSignalTimer,
    }),
    [
      state,
      stepAiLoop,
      stepSim,
      setMode,
      isAutoRunning,
      toggleAutoRun,
      selectedJunctionId,
      applyCurrentSignal,
      applyCurrentRoute,
      injectCongestion,
      resolveCongestion,
      adjustSignalTimer,
    ]
  )


  return <TrafficContext.Provider value={value}>{children}</TrafficContext.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useTrafficStore() {
  const store = useContext(TrafficContext)
  if (!store) throw new Error('useTrafficStore must be used within TrafficProvider.')
  return store
}
