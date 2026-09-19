import { useMemo, useState, type CSSProperties } from 'react'
import { ScrollableRegion } from '../../components/ScrollableRegion/ScrollableRegion'
import shared from './admin-shared.module.css'
import styles from './SessionViewer.module.css'

/**
 * The Gate 0 manual gate (BUILD_BRIEF.md §10 item 14) AND §6.7 item 4,
 * "Event log viewer": "Raw events, filterable by type, with computed
 * view boundaries overlaid so the opening and closing of each view is
 * visible against the underlying events. This is the tool Gate 0's
 * manual check requires, so it exists before this section is built."
 *
 * Raw events on the left, filterable by type; the offline-recomputed
 * canonical views + modes (server/features/replay.py, the exact same
 * pure functions item_view.py and mode.py are tested against) on the
 * right. The "overlay" half of the spec is the colored left border on
 * every raw-event row that falls inside a recomputed view's [start, end)
 * span, in that view's own mode color — the opening and closing of each
 * view is visible directly against the underlying events, not just
 * inferable by cross-referencing two separate tables.
 *
 * Now part of the admin console (§6.7): behind the same auth wall as
 * every other view, reachable from the nav as "Event log."
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
  const [typeFilter, setTypeFilter] = useState<string>('all')

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
      setTypeFilter('all')
    } finally {
      setLoading(false)
    }
  }

  const eventTypes = useMemo(() => Array.from(new Set((events ?? []).map((e) => e.type))).sort(), [events])
  const filteredEvents = useMemo(
    () => (typeFilter === 'all' ? events : (events ?? []).filter((e) => e.type === typeFilter)),
    [events, typeFilter],
  )

  function viewAtTime(t: number): RecomputedView | undefined {
    return views?.find((v) => t >= v.start && t < v.end)
  }

  const MODE_BORDER_COLOR: Record<string, string> = {
    discovery: 'var(--slate)',
    directed_search: 'var(--primary)',
    broad_search: 'var(--primary-hover)',
    comparison: 'var(--warning-ink)',
    refind: 'var(--savings)',
  }

  return (
    <div className={shared.page}>
      <h1 className={shared.title}>Event log</h1>
      <p className={shared.sub}>
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
              <span>{filteredEvents?.length ?? 0}</span>
            </div>
            <div className={shared.toolbar} style={{ padding: 'var(--sp-2) var(--sp-3)', margin: 0, borderBottom: '1px solid var(--line)' }}>
              <button className={[shared.filterBtn, typeFilter === 'all' ? shared.active : ''].join(' ')} onClick={() => setTypeFilter('all')}>
                All types
              </button>
              {eventTypes.map((t) => (
                <button key={t} className={[shared.filterBtn, typeFilter === t ? shared.active : ''].join(' ')} onClick={() => setTypeFilter(t)}>
                  {t}
                </button>
              ))}
            </div>
            <ScrollableRegion
              outerClassName={styles.scrollBodyOuter}
              scrollClassName={styles.scrollBody}
              ariaLabel="raw events"
              arrows={false}
              wheelRedirect={false}
            >
              {!filteredEvents || filteredEvents.length === 0 ? (
                <div className={styles.empty}>No events match this filter.</div>
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
                    {filteredEvents.map((e) => {
                      const overlayView = viewAtTime(e.ts_mono)
                      return (
                        <tr
                          key={e.event_id}
                          className={overlayView ? styles.overlaid : ''}
                          style={overlayView ? ({ '--overlay-color': MODE_BORDER_COLOR[overlayView.mode] ?? 'var(--primary)' } as CSSProperties) : undefined}
                          title={overlayView ? `Inside view: ${overlayView.item_id} (${overlayView.mode})` : undefined}
                        >
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
                      )
                    })}
                  </tbody>
                </table>
              )}
            </ScrollableRegion>
          </div>

          <div className={styles.panel}>
            <div className={styles.panelHeader}>
              <span>Recomputed canonical views</span>
              <span>{views?.length ?? 0}</span>
            </div>
            <ScrollableRegion
              outerClassName={styles.scrollBodyOuter}
              scrollClassName={styles.scrollBody}
              ariaLabel="recomputed canonical views"
              arrows={false}
              wheelRedirect={false}
            >
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
            </ScrollableRegion>
          </div>
        </div>
      ) : null}
    </div>
  )
}
