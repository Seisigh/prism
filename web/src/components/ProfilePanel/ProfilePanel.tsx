import type { ProfileUpdate } from '@prism/sdk'
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { emptyStates } from '../../copy'
import { usePrismSDK } from '../../state/PrismSDKContext'
import { useSession } from '../../state/SessionContext'
import styles from './ProfilePanel.module.css'

interface ProfilePanelProps {
  open: boolean
  onClose: () => void
}

// A dimension's sign tells you which direction it leans; the label pairs
// are functional UI text (not COPY.md-governed marketing copy), kept
// plain and literal on purpose -- this panel is reporting a real,
// fallible model output, not making a claim about the visitor as a
// person.
const DIMENSION_LABELS: Record<string, { positive: string; negative: string }> = {
  price_z: { positive: 'Leans toward higher-priced items', negative: 'Price-conscious' },
  rating: { positive: 'Drawn to highly-rated items', negative: 'Rating matters less' },
  review_count_log: { positive: 'Trusts items with more reviews', negative: 'Review count matters less' },
  on_sale: { positive: 'Drawn to items on sale', negative: 'Not driven by discounts' },
  description_length: { positive: 'Reads the full description', negative: 'Skims past long descriptions' },
  gallery_size: { positive: 'Wants to see more photos', negative: 'Photos matter less' },
  brand_tier: { positive: 'Leans toward premium brands', negative: 'Leans toward value brands' },
}

const MIN_SCORED_VIEWS_FOR_OWN_PROFILE = 3

// The empty state (below 3 scored views) is the real surface + the real
// copy this panel shipped with before Gate 1's modeling work landed.
// Above that threshold, it renders BUILD_BRIEF.md §11's actual taste
// vector, pushed live over the telemetry WebSocket by
// server/ingest/live_scoring.py -- not a placeholder.
export function ProfilePanel({ open, onClose }: ProfilePanelProps) {
  const { consent, setDemo } = useSession()
  const sdk = usePrismSDK()
  const [update, setUpdate] = useState<ProfileUpdate | null>(null)

  useEffect(() => {
    if (!sdk) return
    return sdk.onProfileUpdate(setUpdate)
  }, [sdk])

  useEffect(() => {
    if (!open) return
    setDemo(true)
    sdk?.setDemo(true)
    sdk?.trackPanelOpen()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const declined = consent === 'declined'
  const state = declined ? emptyStates.profileRecordingDeclined : emptyStates.profileBeforeThreeViews
  const hasRealProfile = !declined && update && update.scored_view_count >= MIN_SCORED_VIEWS_FOR_OWN_PROFILE

  const ranked = hasRealProfile
    ? update.dimensions
        .map((dim, i) => ({ dim, weight: update.vector[i] }))
        .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
    : []
  const maxAbsWeight = ranked.length ? Math.max(...ranked.map((d) => Math.abs(d.weight)), 1e-9) : 1

  return (
    <>
      <div className={[styles.overlay, open ? styles.open : ''].join(' ')} onClick={onClose} aria-hidden="true" />
      <aside
        className={[styles.panel, open ? styles.open : ''].join(' ')}
        role="dialog"
        aria-label="Your profile"
        aria-hidden={!open}
      >
        <div className={styles.header}>
          <div className={styles.headingWrap}>
            <span className={styles.spectrumDot} aria-hidden="true" />
            <h2 className={styles.heading}>Your profile</h2>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close profile panel">
            <X size={18} />
          </button>
        </div>
        <div className={styles.body}>
          {hasRealProfile ? (
            <div>
              <p className={styles.emptyBody}>Based on {update.scored_view_count} items you've looked at this session.</p>
              {ranked.map(({ dim, weight }) => {
                const labels = DIMENSION_LABELS[dim]
                const label = labels ? (weight >= 0 ? labels.positive : labels.negative) : dim
                const widthPct = Math.max(4, (Math.abs(weight) / maxAbsWeight) * 100)
                return (
                  <div key={dim} className={styles.dimension}>
                    <div className={styles.dimensionLabel}>
                      <span>{label}</span>
                    </div>
                    <div className={styles.dimensionTrack}>
                      <div
                        className={styles.dimensionFill}
                        style={{ width: `${widthPct}%`, background: 'var(--spectrum-5)' }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon} aria-hidden="true" />
              <h3 className={styles.emptyHeading}>{state.heading}</h3>
              <p className={styles.emptyBody}>{state.body}</p>
              {!declined && (
                <div className={styles.progressRow} aria-hidden="true">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className={[styles.progressDot, (update?.scored_view_count ?? 0) > i ? styles.filled : ''].join(' ')} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
