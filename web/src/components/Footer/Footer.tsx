import { Link } from 'react-router-dom'
import { useSession } from '../../state/SessionContext'
import styles from './Footer.module.css'

export function Footer() {
  const { consent, code } = useSession()

  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.brand}>
          <svg width="120" height="23" viewBox="0 0 168 32" role="img" aria-label="PRISM">
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
          <p className={styles.brandTag}>
            A research prototype storefront. Not a real store, not affiliated with any retailer.
          </p>
        </div>

        <div className={styles.columns}>
          <div className={styles.column}>
            <span className={styles.columnHeading}>Privacy</span>
            <Link className={styles.columnLink} to="/what-gets-recorded">
              What gets recorded
            </Link>
            <Link className={styles.columnLink} to="/delete-my-data">
              Delete my data
            </Link>
          </div>
          <div className={styles.column}>
            <span className={styles.columnHeading}>Catalog</span>
            <Link className={styles.columnLink} to="/category/Home%20%26%20Furniture">
              Home &amp; Furniture
            </Link>
            <Link className={styles.columnLink} to="/cart">
              Cart
            </Link>
          </div>
          <div className={styles.column}>
            <span className={styles.columnHeading}>About</span>
            <a className={styles.columnLink} href="https://github.com/Seisigh/prism" target="_blank" rel="noreferrer">
              Source on GitHub
            </a>
          </div>
        </div>
      </div>

      <div className={styles.legal}>
        <span>
          {consent === 'accepted' && code ? `Your code: ${code}` : 'Recording off'}
        </span>
        <span>&middot;</span>
        <span>Data is pseudonymous, kept 90 days, deleted on request.</span>
      </div>
    </footer>
  )
}
