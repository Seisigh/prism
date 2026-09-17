import { Link } from 'react-router-dom'
import { consent } from '../../copy'
import { useSession } from '../../state/SessionContext'
import { Button } from '../Button/Button'
import styles from './ConsentGate.module.css'

export function ConsentGate() {
  const { accept, decline, pendingCode } = useSession()

  return (
    <div className={styles.screen} role="dialog" aria-modal="true" aria-labelledby="consent-heading">
      <div className={styles.brandPanel}>
        <div className={styles.brandLogo}>
          <svg width="140" height="27" viewBox="0 0 168 32" role="img" aria-label="PRISM">
            <path d="M1 16 H11" stroke="rgba(255,255,255,0.5)" strokeWidth="2" strokeLinecap="round" />
            <path d="M20.5 16 L31 10.5" stroke="#E8432F" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M20.5 16 L31 14" stroke="#E88B2F" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M20.5 16 L31 17.5" stroke="#3FA654" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M20.5 16 L31 21" stroke="#3D8FDB" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M16 5 L27 26 H5 Z" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            <text x="44" y="22" fontFamily="Inter, sans-serif" fontSize="19" fontWeight={600} letterSpacing="3.4" fill="#FFFFFF">
              PRISM
            </text>
          </svg>
        </div>
        <div className={styles.brandMark} aria-hidden="true">
          <svg viewBox="0 0 200 200" role="presentation">
            <path d="M20 100 H78" stroke="rgba(255,255,255,0.28)" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M118 100 L182 62" stroke="#E8432F" strokeWidth="2.5" strokeLinecap="round" opacity="0.92" />
            <path d="M118 100 L182 82" stroke="#E88B2F" strokeWidth="2.5" strokeLinecap="round" opacity="0.92" />
            <path d="M118 100 L182 100" stroke="#D9C534" strokeWidth="2.5" strokeLinecap="round" opacity="0.92" />
            <path d="M118 100 L182 118" stroke="#3FA654" strokeWidth="2.5" strokeLinecap="round" opacity="0.92" />
            <path d="M118 100 L182 138" stroke="#3D8FDB" strokeWidth="2.5" strokeLinecap="round" opacity="0.92" />
            <path d="M118 100 L182 156" stroke="#6B4FD9" strokeWidth="2.5" strokeLinecap="round" opacity="0.92" />
            <path d="M100 30 L142 100 L58 100 Z" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
        </div>
        <div className={styles.brandFooter}>
          <p className={styles.brandTagline}>A research instrument, dressed as a storefront.</p>
          <p className={styles.brandSub}>
            Every view, hover and scroll becomes a calibrated read on interest — visible to you, in real time, in the
            profile panel.
          </p>
        </div>
      </div>

      <div className={styles.formPanel}>
        <div className={styles.card}>
          <svg className={styles.mobileLogo} width="140" height="27" viewBox="0 0 168 32" role="img" aria-label="PRISM">
            <path d="M1 16 H11" stroke="#5A616E" strokeWidth="2" strokeLinecap="round" />
            <path d="M20.5 16 L31 10.5" stroke="#E8432F" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M20.5 16 L31 14" stroke="#E88B2F" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M20.5 16 L31 17.5" stroke="#3FA654" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M20.5 16 L31 21" stroke="#3D8FDB" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M16 5 L27 26 H5 Z" fill="none" stroke="#14161C" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            <text x="44" y="22" fontFamily="Inter, sans-serif" fontSize="19" fontWeight={600} letterSpacing="3.4" fill="#14161C">
              PRISM
            </text>
          </svg>
          <h1 id="consent-heading" className={styles.heading}>
            {consent.heading}
          </h1>

          <div className={styles.body}>
            {consent.body.map((paragraph, i) => (
              <p key={i}>{paragraph}</p>
            ))}
          </div>

          <div className={styles.actions}>
            <Button variant="primary" onClick={accept}>
              {consent.primaryButton}
            </Button>
            <Button variant="secondary" onClick={decline}>
              {consent.secondaryButton}
            </Button>
          </div>

          <div className={styles.footer}>
            <span>
              {consent.footerCodePrefix} <code>{pendingCode}</code>
            </span>
            <Link to="/what-gets-recorded">What gets recorded</Link>
            <Link to="/delete-my-data">Delete my data</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
