import { useState } from 'react'
import styles from './SessionViewer.module.css'

/**
 * The Gate 0 manual gate (BUILD_BRIEF.md §10 item 14): "The author can
 * browse one session, open the raw event log, and confirm by hand that
 * view boundaries and modes match what actually happened." This page is
 * that tool — raw events on the left, the offline-recomputed canonical
 * views + modes (server/features/replay.py, the exact same pure
 * functions item_view.py and mode.py are tested against) on the right,
 * so the two can be checked side by side against what was actually done
 * in the browser.
 *
 * Not part of the consumer storefront — no nav link points here, it's a
 * diagnostic the author navigates to directly by code. Gate 0 has no
 * admin auth wall yet (flagged in STATE.md); the whole site is
 * noindex + consent-gated + not yet publicly deployed, so this is an
 * acceptable simplification for now, not a real production admin surface.
 */

interface RawEvent {
  event_id: string
  seq: number
  ts_mono: number
  ts_wall: string
  demo: boolean
  surface: string
  mode: string | null
  type: string
  payload: Record<string, unknown>
}

interface RecomputedView {
  item_id: string
  surface: string
  start: number
  end: number
  duration_ms: number
  mode: string
  closed_by: string
}

export function SessionViewer() {
  const [codeInput, setCodeInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [events, setEvents] = useState<RawEvent[] | null>(null)
  const [views, setViews] = useState<RecomputedView[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load(input: string) {
    setError(null)
    setLoading(true)
    setEvents(null)
    setViews(null)
    try {
      let resolvedId = input
      // A code looks like "a7f3-92kd"; a session_id is a UUID. If it's
      // not UUID-shaped, resolve it as a code first.
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(input)) {
        const res = await fetch(`/api/sessions/by-code/${encodeURIComponent(input)}`)
        if (!res.ok) throw new Error('No session found under that code')
        const data = await res.json()
        resolvedId = data.session_ids[data.session_ids.length - 1]
      }
      setSessionId(resolvedId)
      const [eventsRes, viewsRes] = await Promise.all([
        fetch(`/api/sessions/${resolvedId}/events`),
        fetch(`/api/sessions/${resolvedId}/views`),
      ])
      if (!eventsRes.ok) throw new Error('Failed to load events')
      const eventsData = await eventsRes.json()
      const viewsData = viewsRes.ok ? await viewsRes.json() : { views: [] }
      setEvents(eventsData.events)
      setViews(viewsData.views)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load session')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Session event-log viewer</h1>
      <p className={styles.sub}>
        Raw events (left) against the offline-recomputed canonical views and modes (right) —
        server/features/item_view.py and mode.py run against the stored log, the same pure functions
        the fixture tests exercise.
      </p>

      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault()
          if (codeInput.trim()) load(codeInput.trim())
        }}
      >
        <input
          className={styles.input}
          value={codeInput}
          onChange={(e) => setCodeInput(e.target.value)}
          placeholder="Session code (a7f3-92kd) or session_id"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Load'}
        </button>
      </form>

      {error ? <p style={{ color: 'var(--danger)' }}>{error}</p> : null}
      {sessionId ? (
        <p style={{ fontSize: 'var(--fs-12)', color: 'var(--slate-soft)', marginTop: -24, marginBottom: 24 }}>
          session_id: <code>{sessionId}</code>
        </p>
      ) : null}

      {events ? (
        <div className={styles.columns}>
          <div className={styles.panel}>
            <div className={styles.panelHeader}>
              <span>Raw events</span>
              <span>{events.length}</span>
            </div>
            <div className={styles.scrollBody}>
              {events.length === 0 ? (
                <div className={styles.empty}>No events recorded under this session.</div>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>seq</th>
                      <th>t (ms)</th>
                      <th>surface</th>
                      <th>mode</th>
                      <th>type</th>
                      <th>payload</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e) => (
                      <tr key={e.event_id}>
                        <td>{e.seq}</td>
                        <td>{e.ts_mono.toFixed(0)}</td>
                        <td>{e.surface}</td>
                        <td>
                          {e.mode ? (
                            <span className={[styles.modeTag, styles[`mode-${e.mode}`]].join(' ')}>{e.mode}</span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td>{e.type}</td>
                        <td className={styles.payload}>{JSON.stringify(e.payload)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className={styles.panel}>
            <div className={styles.panelHeader}>
              <span>Recomputed canonical views</span>
              <span>{views?.length ?? 0}</span>
            </div>
            <div className={styles.scrollBody}>
              {!views || views.length === 0 ? (
                <div className={styles.empty}>
                  No canonical views recomputed (no qualifying 300ms+ exposure in this log).
                </div>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>item_id</th>
                      <th>surface</th>
                      <th>start</th>
                      <th>end</th>
                      <th>duration</th>
                      <th>mode</th>
                      <th>closed_by</th>
                    </tr>
                  </thead>
                  <tbody>
                    {views.map((v, i) => (
                      <tr key={i}>
                        <td>{v.item_id}</td>
                        <td>{v.surface}</td>
                        <td>{v.start.toFixed(0)}</td>
                        <td>{v.end.toFixed(0)}</td>
                        <td>{v.duration_ms.toFixed(0)}ms</td>
                        <td>
                          <span className={[styles.modeTag, styles[`mode-${v.mode}`]].join(' ')}>{v.mode}</span>
                        </td>
                        <td>{v.closed_by}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
