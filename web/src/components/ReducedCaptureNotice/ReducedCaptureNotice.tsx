import { useEffect, useState } from 'react'
import { reducedCaptureNotice } from '../../copy'
import styles from './ReducedCaptureNotice.module.css'

// §7.3: touch has no hover, so the motor signal family is unavailable —
// gated on (hover: none), not just viewport width, so a narrow desktop
// window (still mouse-driven) doesn't show a touch-specific notice.
export function ReducedCaptureNotice() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(hover: none) and (pointer: coarse) and (max-width: 767px)')
    setShow(mq.matches)
    const onChange = () => setShow(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  if (!show) return null

  return <div className={styles.notice}>{reducedCaptureNotice}</div>
}
