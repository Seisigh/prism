import { useEffect, useState } from 'react'
import shared from './admin-shared.module.css'
import styles from './Season.module.css'

const SEASON_LABELS: Record<string, string> = {
  none: 'None',
  spring: 'Spring',
  summer: 'Summer',
  fall: 'Fall',
  winter: 'Winter',
  holiday: 'Holiday',
}

export function Season() {
  const [current, setCurrent] = useState<string | null>(null)
  const [validSeasons, setValidSeasons] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  function load() {
    setError(null)
    fetch('/api/admin/season')
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load the active season')
        return r.json()
      })
      .then((d) => {
        setCurrent(d.season)
        setValidSeasons(d.valid_seasons)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load the active season'))
  }

  useEffect(load, [])

  async function setSeason(season: string) {
    setSaving(season)
    setError(null)
    try {
      const res = await fetch('/api/admin/season', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ season }),
      })
      if (!res.ok) throw new Error('Failed to set the active season')
      const d = await res.json()
      setCurrent(d.season)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set the active season')
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.title}>Season</h1>
          <p className={shared.sub}>
            Merchandising only — which items surface on the home page's seasonal rail and get a seasonal badge. Never
            reaches the feature pipeline, the ranker, or scoring. Logged once on every new session so its effect on
            behavior is measurable later.
          </p>
        </div>
      </div>

      <div className={shared.panel}>
        <div className={shared.panelHeader}>
          <span>Active season</span>
        </div>
        <div className={styles.body}>
          {error ? <p className={shared.errorText}>{error}</p> : null}
          {current === null && !error ? (
            <div className={shared.loading}>Loading…</div>
          ) : (
            <div className={styles.buttonRow}>
              {validSeasons.map((season) => (
                <button
                  key={season}
                  className={[styles.seasonBtn, current === season ? styles.active : ''].join(' ')}
                  onClick={() => setSeason(season)}
                  disabled={saving !== null}
                  aria-pressed={current === season}
                >
                  {SEASON_LABELS[season] ?? season}
                  {saving === season ? '…' : current === season ? ' ✓' : ''}
                </button>
              ))}
            </div>
          )}
          <p className={styles.note}>
            Setting a season with too few tagged items (fewer than 6) won't add a home-page rail — the storefront
            falls back to its ordinary category rails, never a padded or fabricated one.
          </p>
        </div>
      </div>
    </div>
  )
}
