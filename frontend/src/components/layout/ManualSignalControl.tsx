/* oxlint-disable react/only-export-components */
import { useEffect, useRef, useState } from 'react'
import type { ConnectionStatus } from '../../state/trafficStore'
import type { ControlMode, HealthResponse, SignalActuationResult, TrafficState } from '../../types/traffic'

export const MIN_MANUAL_GREEN_SECONDS = 5
export const MAX_MANUAL_GREEN_SECONDS = 180

type Availability = { enabled: boolean; reason: string | null }
export function manualSignalAvailability({ health, status, mode, intersectionId, intersectionAvailable, duration, submitting }: { health: HealthResponse | null; status: ConnectionStatus; mode: ControlMode | null; intersectionId: string | null; intersectionAvailable: boolean; duration: number; submitting: boolean }): Availability {
  if (health?.simulation_connected !== true || status === 'backend-unavailable' || status === 'sumo-unavailable') return { enabled: false, reason: 'SUMO and backend connectivity are required before a manual command can be sent.' }
  if (mode !== 'MANUAL') return { enabled: false, reason: mode === 'AUTO' ? 'Manual commands are disabled while backend-confirmed mode is AUTO.' : mode === 'EMERGENCY' ? 'Manual commands are disabled while backend-confirmed mode is EMERGENCY.' : 'Waiting for the backend-confirmed control mode.' }
  if (!intersectionId || !intersectionAvailable) return { enabled: false, reason: 'Select a valid backend intersection before sending a manual command.' }
  if (!Number.isFinite(duration) || duration < MIN_MANUAL_GREEN_SECONDS || duration > MAX_MANUAL_GREEN_SECONDS) return { enabled: false, reason: `Requested green duration must be between ${MIN_MANUAL_GREEN_SECONDS} and ${MAX_MANUAL_GREEN_SECONDS} seconds.` }
  if (submitting) return { enabled: false, reason: 'A manual signal command is already being submitted.' }
  return { enabled: true, reason: null }
}

export function ManualSignalControl({ intersectionId, intersectionAvailable, traffic, health, status, mode, onApply }: { intersectionId: string; intersectionAvailable: boolean; traffic: TrafficState | undefined; health: HealthResponse | null; status: ConnectionStatus; mode: ControlMode | null; onApply: (target: string, duration: number) => Promise<SignalActuationResult> }) {
  const [durationValue, setDurationValue] = useState('30')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<SignalActuationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const submissionRef = useRef(false)
  const selectionRef = useRef(intersectionId)
  const duration = Number(durationValue)
  const availability = manualSignalAvailability({ health, status, mode, intersectionId, intersectionAvailable, duration, submitting })

  useEffect(() => {
    if (selectionRef.current === intersectionId) return
    selectionRef.current = intersectionId
    if (!submissionRef.current) { setResult(null); setError(null) }
  }, [intersectionId])

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!availability.enabled || submissionRef.current) return
    const targetAtSubmission = intersectionId
    submissionRef.current = true
    setSubmitting(true); setError(null); setResult(null)
    try {
      const confirmed = await onApply(targetAtSubmission, duration)
      setResult(confirmed)
    } catch (submissionError) { setError(submissionError instanceof Error ? submissionError.message : 'Unable to apply manual signal timing.') }
    finally { submissionRef.current = false; setSubmitting(false) }
  }

  return <section className="intel-card manual-signal-control" aria-labelledby="manual-signal-title">
    <div className="intel-title"><span id="manual-signal-title">Manual signal control</span><span className={`manual-mode mode-${mode?.toLowerCase() ?? 'unknown'}`}>{mode ?? '—'}</span></div>
    <div className="manual-observed"><span>Observed state</span><b>{traffic?.signal_phase ?? 'Awaiting telemetry'}</b><small>{traffic ? `${traffic.green_remaining.toFixed(1)}s green remaining` : 'No backend signal state received'}</small></div>
    <form onSubmit={(event) => { void submit(event) }}>
      <label htmlFor={`manual-duration-${intersectionId}`}>Requested green duration <span>(seconds)</span></label>
      <div className="manual-input-row"><input id={`manual-duration-${intersectionId}`} name="green-duration" type="number" min={MIN_MANUAL_GREEN_SECONDS} max={MAX_MANUAL_GREEN_SECONDS} step="1" inputMode="decimal" value={durationValue} onChange={(event) => setDurationValue(event.target.value)} aria-describedby={`manual-help-${intersectionId}`} disabled={submitting} /><button type="submit" disabled={!availability.enabled} aria-busy={submitting}>{submitting ? 'Applying…' : 'Apply signal timing'}</button></div>
      <p id={`manual-help-${intersectionId}`} className="manual-help">Target <b>{intersectionId}</b> · permitted range {MIN_MANUAL_GREEN_SECONDS}–{MAX_MANUAL_GREEN_SECONDS}s · source MANUAL</p>
    </form>
    <div className="manual-announcement" role="status" aria-live="polite">{error ? <span className="manual-error">{error}</span> : result ? <span className={result.success ? 'manual-success' : 'manual-error'}>{result.success ? `Confirmed for ${result.target}: ${result.applied_duration.toFixed(1)}s ${result.current_phase.toLowerCase()} (${result.applied_to}).` : result.message}</span> : availability.reason ? <span>{availability.reason}</span> : <span>Ready to request a backend-confirmed manual timing update.</span>}</div>
    {result && <p className="manual-result-detail">{result.message} Result target: {result.target}; selection changes do not redirect an in-flight command.</p>}
  </section>
}
