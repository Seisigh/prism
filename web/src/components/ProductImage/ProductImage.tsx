import { useState } from 'react'
import { mediaUrl } from '../../lib/api'
import styles from './ProductImage.module.css'

interface ProductImageProps {
  path: string | null
  alt: string
  eager?: boolean
  className?: string
}

export function ProductImage({ path, alt, eager = false, className }: ProductImageProps) {
  const [loaded, setLoaded] = useState(false)
  return (
    <div className={[styles.frame, className].filter(Boolean).join(' ')}>
      {!loaded && <div className={styles.skeleton} aria-hidden="true" />}
      {path ? (
        <img
          className={[styles.img, loaded ? styles.loaded : ''].join(' ')}
          src={mediaUrl(path)}
          alt={alt}
          loading={eager ? 'eager' : 'lazy'}
          onLoad={() => setLoaded(true)}
        />
      ) : null}
    </div>
  )
}
