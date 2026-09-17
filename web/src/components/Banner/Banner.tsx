import { useState } from 'react'
import { X } from 'lucide-react'
import { banner } from '../../copy'
import styles from './Banner.module.css'

const DISMISS_KEY = 'prism.banner.dismissed'

export function Banner() {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === '1'
    } catch {
      return false
    }
  })

  if (dismissed) return null

  const dismiss = () => {
    setDismissed(true)
    try {
      sessionStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* non-fatal */
    }
  }

  return (
    <div className={styles.banner}>
      <span className={styles.text}>{banner.text}</span>
      <button className={styles.dismiss} onClick={dismiss} aria-label="Dismiss banner">
        <X size={14} strokeWidth={2.5} />
      </button>
    </div>
  )
}
