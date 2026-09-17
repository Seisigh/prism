import { X } from 'lucide-react'
import { useEffect } from 'react'
import { emptyStates } from '../../copy'
import { usePrismSDK } from '../../state/PrismSDKContext'
import { useSession } from '../../state/SessionContext'
import styles from './ProfilePanel.module.css'

interface ProfilePanelProps {
  open: boolean
  onClose: () => void
}

// Real profile data (the taste vector + signal weights from BUILD_BRIEF
// §11) doesn't exist until Gate 1's modeling work lands. This panel is
// the real surface + the real empty-state copy; it's wired to session
// state truthfully rather than faked with placeholder numbers.
export function ProfilePanel({ open, onClose }: ProfilePanelProps) {
  const { consent, setDemo } = useSession()
  const sdk = usePrismSDK()

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
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon} aria-hidden="true" />
            <h3 className={styles.emptyHeading}>{state.heading}</h3>
            <p className={styles.emptyBody}>{state.body}</p>
            {!declined && (
              <div className={styles.progressRow} aria-hidden="true">
                {[0, 1, 2].map((i) => (
                  <span key={i} className={styles.progressDot} />
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}
