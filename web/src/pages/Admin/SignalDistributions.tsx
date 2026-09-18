import { useEffect, useState } from 'react'
import shared from './admin-shared.module.css'
import styles from './SignalDistributions.module.css'

interface Stratum {
  mode: string
  surface: string
  n: number
  n_available: number
  availability_rate: number
  histogram: { bin_edges: number[]; counts: number[] }
}

type Distributions = Record<string, Record<string, Stratum>>

export function SignalDistributions() {
  const [data, setData] = useState<{ n_sessions: number; distributions: Distributions } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/admin/signal-distributions')
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load signal distributions')
        return r.json()
      })
      .then((d) => {
        setData(d)
        const names = Object.keys(d.distributions).sort()
        if (names.length) setSelected(names[0])
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load signal distributions'))
  }, [])

  const signalNames = data ? Object.keys(data.distributions).sort() : []
  const strata = selected && data ? Object.values(data.distributions[selected]) : []

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.title}>Signal distributions</h1>
          <p className={shared.sub}>
            Per signal, per mode, per surface: a histogram of raw values plus the real availability rate — this is how a
            degenerate normalizer or a signal that's null on every detail page gets noticed before it silently corrupts a
            model. {data ? `Computed across ${data.n_sessions} stored session${data.n_sessions === 1 ? '' : 's'}.` : null}
          </p>
        </div>
      </div>

      {error ? (
        <p className={shared.errorText}>{error}</p>
      ) : data === null ? (
        <div className={shared.loading}>Loading…</div>
      ) : signalNames.length === 0 ? (
        <div className={shared.empty}>No signal data yet — browse a session first.</div>
      ) : (
        <div className={styles.layout}>
          <div className={styles.signalList}>
            {signalNames.map((name) => (
              <button
                key={name}
                className={[styles.signalItem, selected === name ? styles.active : ''].join(' ')}
                onClick={() => setSelected(name)}
              >
                {name}
              </button>
            ))}
          </div>

          <div className={styles.strataGrid}>
            {strata.length === 0 ? (
              <p className={styles.noData}>No strata recorded for this signal yet.</p>
            ) : (
              strata.map((s) => {
                const maxCount = Math.max(1, ...s.histogram.counts)
                const lowAvailability = s.availability_rate < 0.5
                return (
                  <div key={`${s.mode}|${s.surface}`} className={styles.stratumCard}>
                    <div className={styles.stratumHeader}>
                      <span className={styles.stratumTitle}>
                        <span className={[shared.modeTag, shared[`mode-${s.mode}`]].join(' ')} style={{ marginRight: 6 }}>
                          {s.mode.replace('_', ' ')}
                        </span>
                        {s.surface}
                      </span>
                      <span className={[styles.availabilityRate, lowAvailability ? styles.low : ''].join(' ')}>
                        {(s.availability_rate * 100).toFixed(0)}% available (n={s.n})
                      </span>
                    </div>
                    {s.histogram.counts.length === 0 ? (
                      <p className={styles.noData}>No available values in this stratum.</p>
                    ) : (
                      <div className={styles.histogram}>
                        {s.histogram.counts.map((c, i) => {
                          const lo = s.histogram.bin_edges[i]
                          const hi = s.histogram.bin_edges[i + 1]
                          const range = lo !== undefined && hi !== undefined ? `[${lo.toFixed(3)}, ${hi.toFixed(3)})` : ''
                          return (
                            <div
                              key={i}
                              className={styles.bar}
                              style={{ height: `${Math.max(4, (c / maxCount) * 64)}px` }}
                              title={`${range} — ${c} view${c === 1 ? '' : 's'}`}
                            />
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
