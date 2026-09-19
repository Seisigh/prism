import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ScrollableRegion } from '../../components/ScrollableRegion/ScrollableRegion'
import shared from './admin-shared.module.css'
import styles from './SessionsList.module.css'

interface AdminSession {
  session_id: string
  code: string
  created_at: string
  last_event_at: string | null
  demo_opened: boolean
  browser: string | null
  device_pixel_ratio: number | null
  viewport_width: number | null
  viewport_height: number | null
  pointer_type: string | null
  item_views: number
  commitments: number
  duration_ms: number | null
  mode_distribution: Record<string, number>
}

type CommitmentFilter = 'any' | 'with' | 'without'

const MODE_ORDER = ['discovery', 'directed_search', 'broad_search', 'comparison', 'refind']

function formatDuration(ms: number | null): string {
  if (ms === null || ms < 0) return '—'
  const totalSeconds = Math.round(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}m ${seconds}s`
}

export function SessionsList() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<AdminSession[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [demoFilter, setDemoFilter] = useState<'all' | 'real' | 'demo'>('all')
  const [commitmentFilter, setCommitmentFilter] = useState<CommitmentFilter>('any')

  useEffect(() => {
    const params = new URLSearchParams()
    if (demoFilter === 'real') params.set('real_only', 'true')
    if (demoFilter === 'demo') params.set('demo_only', 'true')
    if (commitmentFilter !== 'any') params.set('has_commitment', String(commitmentFilter === 'with'))

    setSessions(null)
    setError(null)
    fetch(`/api/admin/sessions?${params.toString()}`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load sessions')
        return r.json()
      })
      .then((d) => setSessions(d.sessions))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load sessions'))
  }, [demoFilter, commitmentFilter])

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.title}>Sessions</h1>
          <p className={shared.sub}>All sessions, newest first. Pseudonymous codes only — never an IP, never a name.</p>
        </div>
      </div>

      <div className={shared.toolbar}>
        <div className={styles.filterGroup}>
          <span className={styles.filterGroupLabel}>Recording</span>
          {(['all', 'real', 'demo'] as const).map((v) => (
            <button
              key={v}
              className={[shared.filterBtn, demoFilter === v ? shared.active : ''].join(' ')}
              onClick={() => setDemoFilter(v)}
            >
              {v === 'all' ? 'All sessions' : v === 'real' ? 'Real only' : 'Demo only'}
            </button>
          ))}
        </div>
        <div className={styles.filterGroup}>
          <span className={styles.filterGroupLabel}>Commitment</span>
          {(['any', 'with', 'without'] as const).map((v) => (
            <button
              key={v}
              className={[shared.filterBtn, commitmentFilter === v ? shared.active : ''].join(' ')}
              onClick={() => setCommitmentFilter(v)}
            >
              {v === 'any' ? 'Any' : v === 'with' ? 'Has commitment' : 'No commitment'}
            </button>
          ))}
        </div>
      </div>

      <div className={shared.panel}>
        <div className={shared.panelHeader}>
          <span>Sessions</span>
          <span>{sessions?.length ?? '—'}</span>
        </div>
        {error ? (
          <p className={shared.errorText}>{error}</p>
        ) : sessions === null ? (
          <div className={shared.loading}>Loading…</div>
        ) : sessions.length === 0 ? (
          <div className={shared.empty}>No sessions match these filters.</div>
        ) : (
          <ScrollableRegion outerClassName={shared.tableScrollOuter} scrollClassName={shared.tableScroll} ariaLabel="sessions">
          <table className={shared.table}>
            <thead>
              <tr>
                <th>Code</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Item views</th>
                <th>Commitments</th>
                <th>Mode distribution</th>
                <th>Browser / device</th>
                <th>Demo opened</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr
                  key={s.session_id}
                  className={shared.clickable}
                  onClick={() => navigate(`/admin/sessions/${s.session_id}`)}
                  tabIndex={0}
                  role="button"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      navigate(`/admin/sessions/${s.session_id}`)
                    }
                  }}
                >
                  <td>
                    <Link
                      className={shared.link}
                      to={`/admin/sessions/${s.session_id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {s.code}
                    </Link>
                  </td>
                  <td>{new Date(s.created_at).toLocaleString()}</td>
                  <td>{formatDuration(s.duration_ms)}</td>
                  <td>{s.item_views}</td>
                  <td>{s.commitments}</td>
                  <td>
                    {MODE_ORDER.filter((m) => s.mode_distribution[m]).map((m) => (
                      <span key={m} className={[shared.modeTag, shared[`mode-${m}`]].join(' ')} style={{ marginRight: 4 }}>
                        {m.replace('_', ' ')}
                        <span className={shared.modeCount}>{s.mode_distribution[m]}</span>
                      </span>
                    ))}
                    {Object.keys(s.mode_distribution).length === 0 ? <span className={shared.mono}>—</span> : null}
                  </td>
                  <td className={shared.mono}>
                    {s.browser ?? '—'} · {s.pointer_type ?? '—'}
                  </td>
                  <td>{s.demo_opened ? 'Yes' : 'No'}</td>
                  <td>
                    <Link
                      className={shared.link}
                      to={`/admin/live/${s.session_id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      Live →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </ScrollableRegion>
        )}
      </div>
    </div>
  )
}
