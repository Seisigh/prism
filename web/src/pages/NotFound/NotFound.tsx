import { PackageX } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/Button/Button'
import { errors } from '../../copy'
import styles from '../../styles/contentPage.module.css'

export function NotFound() {
  return (
    <div className={styles.page} style={{ textAlign: 'center', paddingTop: 'var(--sp-16)' }}>
      <PackageX size={40} strokeWidth={1.5} style={{ color: 'var(--slate-soft)', marginBottom: 'var(--sp-4)' }} />
      <h1 className={styles.title}>{errors.itemNotFound.heading}</h1>
      <p className={styles.section} style={{ margin: '0 auto var(--sp-6)' }}>
        {errors.itemNotFound.body}
      </p>
      <Link to="/">
        <Button variant="primary">{errors.itemNotFound.action}</Button>
      </Link>
    </div>
  )
}
