/* oxlint-disable react/only-export-components */
import { useState } from 'react'
import type { ActionHistoryRecord } from '../../state/trafficStore'

export function filterActionHistory(records: ActionHistoryRecord[], typeFilter: 'ALL' | 'SIGNAL' | 'ROUTE', statusFilter: 'ALL' | 'SUCCESS' | 'FAILURE') {
  return records.filter((record) => (typeFilter === 'ALL' || record.kind === typeFilter) && (statusFilter === 'ALL' || statusFilter === 'SUCCESS' && record.success === true || statusFilter === 'FAILURE' && record.success === false))
}

export function ActionHistory({ records }: { records: ActionHistoryRecord[] }) {
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'SIGNAL' | 'ROUTE'>('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'SUCCESS' | 'FAILURE'>('ALL')
  const shown = filterActionHistory(records, typeFilter, statusFilter)
  return <section className="intel-card action-history" aria-labelledby="action-history-title"><div className="intel-title"><span id="action-history-title">Action history</span><span className="panel-label">SESSION ONLY</span></div><div className="history-filters" role="group" aria-label="Filter action type">{(['ALL', 'SIGNAL', 'ROUTE'] as const).map((item) => <button key={item} aria-pressed={typeFilter === item} onClick={() => setTypeFilter(item)}>{item}</button>)}</div><div className="history-filters" role="group" aria-label="Filter action status">{(['ALL', 'SUCCESS', 'FAILURE'] as const).map((item) => <button key={item} aria-pressed={statusFilter === item} onClick={() => setStatusFilter(item)}>{item}</button>)}</div>{shown.length ? <div className="history-list">{shown.map((record) => <details key={record.id}><summary><b>{record.kind}</b><span>{record.target ?? 'Unavailable target'}</span><em>{record.success === true ? 'Confirmed' : record.success === false ? 'Failed' : 'Reported'}</em></summary><p>{record.source ? `Source ${record.source} · ` : ''}Client observed {new Date(record.observedAt).toLocaleTimeString()}</p>{typeof record.details.message === 'string' && <p>{record.details.message}</p>}</details>)}</div> : <p className="empty-telemetry">No matching actions in this browser session.</p>}</section>
}
