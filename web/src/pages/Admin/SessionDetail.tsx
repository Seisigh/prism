import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import shared from './admin-shared.module.css'
import styles from './SessionDetail.module.css'

interface SignalValue {
  raw: number | null
  normalized: number | null
  available: boolean
}

interface SignalRow {
  item_id: string
  item_known: boolean
  surface: string
  mode: string
  start: number
  end: number
  duration_ms: number
  predicted_p_i: number | null
  label: 'committed' | 'fast_skip' | 'ambiguous'
  signals: Record<string, SignalValue>
}

function fmt(n: number | null): string {
  if (n === null) return '—'
  return Number.isInteger(n) ? String(n) : n.toFixed(3)
}

export function SessionDetail() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [rows, setRows] = useState<SignalRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    if (!sessionId) return
    setRows(null)
    setError(null)
    fetch(`/api/admin/sessions/${sessionId}/signals`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load session signals')
        return r.json()
      })
      .then((d) => setRows(d.rows))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load session signals'))
  }, [sessionId])

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.title}>Session detail</h1>
          <p className={shared.sub}>
            <Link className={shared.link} to="/admin/sessions">
              ← All sessions
            </Link>{' '}
            · <span className={shared.mono}>{sessionId}</span>
          </p>
        </div>
      </div>

      <div className={shared.panel}>
        <div className={shared.panelHeader}>
          <span>Item views — click a row for the full signal breakdown</span>
          <span>{rows?.length ?? '—'}</span>
        </div>
        {error ? (
          <p className={shared.errorText}>{error}</p>
        ) : rows === null ? (
          <div className={shared.loading}>Loading…</div>
        ) : rows.length === 0 ? (
          <div className={shared.empty}>No qualifying views in this session yet.</div>
        ) : (
          <div className={shared.tableScroll}>
          <table className={shared.table}>
            <thead>
              <tr>
                <th>Item</th>
                <th>Surface</th>
                <th>Mode</th>
                <th>Duration</th>
                <th>Predicted p_i</th>
                <th>Label</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <Fragment key={i}>
                  <tr
                    className={shared.clickable}
                    onClick={() => setExpanded(expanded === i ? null : i)}
                    tabIndex={0}
                    role="button"
                    aria-expanded={expanded === i}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setExpanded(expanded === i ? null : i)
                      }
                    }}
                  >
                    <td className={shared.mono}>
                      {row.item_id}
                      {!row.item_known ? ' ⚠' : ''}
                    </td>
                    <td>{row.surface}</td>
                    <td>
                      <span className={[shared.modeTag, shared[`mode-${row.mode}`]].join(' ')}>{row.mode.replace('_', ' ')}</span>
                    </td>
                    <td>{Math.round(row.duration_ms)}ms</td>
                    <td className={styles.pScore}>{row.predicted_p_i === null ? '—' : row.predicted_p_i.toFixed(3)}</td>
                    <td>
                      <span className={[shared.labelTag, shared[`label-${row.label}`]].join(' ')}>{row.label.replace('_', ' ')}</span>
                    </td>
                  </tr>
                  {expanded === i ? (
                    <tr className={styles.expandRow}>
                      <td colSpan={6}>
                        <div className={styles.signalGrid}>
                          {Object.entries(row.signals)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([name, v]) => (
                              <div key={name} className={styles.signalCard}>
                                <div className={styles.signalName}>
                                  <span className={[shared.availDot, v.available ? shared.availYes : shared.availNo].join(' ')} />
                                  {name}
                                </div>
                                {v.available ? (
                                  <div className={styles.signalValues}>
                                    <span>
                                      raw <b>{fmt(v.raw)}</b>
                                    </span>
                                    <span>
                                      z <b>{fmt(v.normalized)}</b>
                                    </span>
                                  </div>
                                ) : (
                                  <div className={styles.unavailable}>unavailable — not imputed as zero</div>
                                )}
                              </div>
                            ))}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  )
}
