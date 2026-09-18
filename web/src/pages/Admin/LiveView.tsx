import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import shared from './admin-shared.module.css'
import styles from './LiveView.module.css'

interface LiveEvent {
  event_id: string
  seq: number
  ts_mono: number
  surface: string
  mode: string | null
  type: string
  payload: Record<string, unknown>
}

interface LiveUpdate {
  type: 'live_update'
  new_events: LiveEvent[]
  taste_vector: number[]
  dimensions: string[]
  scored_view_count: number
}

/**
 * §6.7 item 3: "WebSocket-fed, follows an active session as it happens:
 * the event stream, both vectors updating... Freeze and step controls,
 * because watching it at full speed is impressive and useless for
 * finding bugs."
 *
 * The slate half of that spec (current recommendations, score/rail/
 * propensity/core-seeding-boost per item) needs a live recommendation
 * endpoint that does not exist yet (STATE.md: server/recommender/ is
 * built but not wired to a live rail) -- this view shows the event
 * stream and the taste vector, which the current backend genuinely
 * produces, and does not fabricate a slate panel with nothing behind it.
 */
export function LiveView() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [connected, setConnected] = useState(false)
  const [displayedEvents, setDisplayedEvents] = useState<LiveEvent[]>([])
  const [vector, setVector] = useState<{ values: number[]; dims: string[] } | null>(null)
  const [scoredCount, setScoredCount] = useState(0)
  const [frozen, setFrozen] = useState(false)
  const queueRef = useRef<LiveUpdate[]>([])
  const [queueLength, setQueueLength] = useState(0)

  useEffect(() => {
    if (!sessionId) return
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${window.location.host}/api/admin/live/${sessionId}`)
    ws.addEventListener('open', () => setConnected(true))
    ws.addEventListener('close', () => setConnected(false))
    ws.addEventListener('message', (event) => {
      try {
        const update = JSON.parse(event.data) as LiveUpdate
        if (frozenRef.current) {
          queueRef.current.push(update)
          setQueueLength(queueRef.current.length)
        } else {
          applyUpdate(update)
        }
      } catch {
        // ignore malformed frames
      }
    })
    return () => ws.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const frozenRef = useRef(frozen)
  frozenRef.current = frozen

  function applyUpdate(update: LiveUpdate) {
    setDisplayedEvents((prev) => [...update.new_events, ...prev].slice(0, 200))
    setVector({ values: update.taste_vector, dims: update.dimensions })
    setScoredCount(update.scored_view_count)
  }

  function step() {
    const next = queueRef.current.shift()
    setQueueLength(queueRef.current.length)
    if (next) applyUpdate(next)
  }

  function toggleFreeze() {
    setFrozen((f) => {
      const next = !f
      if (!next) {
        // Resuming: drain the queue in order, applying the latest state.
        while (queueRef.current.length) {
          const update = queueRef.current.shift()
          if (update) applyUpdate(update)
        }
        setQueueLength(0)
      }
      return next
    })
  }

  const ranked = vector
    ? vector.dims
        .map((dim, i) => ({ dim, weight: vector.values[i] }))
        .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
    : []
  const maxAbs = ranked.length ? Math.max(...ranked.map((d) => Math.abs(d.weight)), 1e-9) : 1

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.title}>Live view</h1>
          <p className={shared.sub}>
            <span className={[styles.statusDot, connected ? styles.statusConnected : styles.statusDisconnected].join(' ')} />
            {connected ? 'Connected' : 'Disconnected'} · <span className={shared.mono}>{sessionId}</span>
          </p>
        </div>
        <div className={styles.controls}>
          <button className={[styles.controlBtn, frozen ? styles.frozen : ''].join(' ')} onClick={toggleFreeze}>
            {frozen ? 'Resume' : 'Freeze'}
          </button>
          <button className={styles.controlBtn} onClick={step} disabled={!frozen || queueLength === 0}>
            Step
          </button>
          {frozen ? <span className={styles.queueBadge}>{queueLength} update(s) queued</span> : null}
        </div>
      </div>

      <div className={styles.layout}>
        <div className={shared.panel}>
          <div className={shared.panelHeader}>
            <span>Event stream</span>
            <span>{displayedEvents.length}</span>
          </div>
          <div className={styles.stream}>
            {displayedEvents.length === 0 ? (
              <div className={shared.empty}>Waiting for events — this session must be actively browsing.</div>
            ) : (
              <div className={shared.tableScroll}>
              <table className={shared.table}>
                <thead>
                  <tr>
                    <th>t (ms)</th>
                    <th>surface</th>
                    <th>mode</th>
                    <th>type</th>
                    <th>payload</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedEvents.map((e) => (
                    <tr key={e.event_id}>
                      <td>{e.ts_mono.toFixed(0)}</td>
                      <td>{e.surface}</td>
                      <td>
                        {e.mode ? <span className={[shared.modeTag, shared[`mode-${e.mode}`]].join(' ')}>{e.mode}</span> : '—'}
                      </td>
                      <td>{e.type}</td>
                      <td className={[shared.mono, styles.payload].join(' ')}>{JSON.stringify(e.payload)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </div>
        </div>

        <div className={styles.vectorPanel}>
          <div className={styles.vectorTitle}>Taste vector ({scoredCount} scored views)</div>
          {ranked.length === 0 ? (
            <p className={shared.mono} style={{ color: 'var(--slate-soft)' }}>
              No scored views yet.
            </p>
          ) : (
            ranked.map(({ dim, weight }) => (
              <div key={dim} className={styles.dimension}>
                <div className={styles.dimensionLabel}>
                  <span>{dim}</span>
                  <span>{weight.toFixed(3)}</span>
                </div>
                <div className={styles.dimensionTrack}>
                  <div className={styles.dimensionFill} style={{ width: `${Math.max(4, (Math.abs(weight) / maxAbs) * 100)}%` }} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
