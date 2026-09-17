import { useRef, useState } from 'react'
import { mediaUrl } from '../../lib/api'
import type { ImageSet } from '../../lib/types'
import styles from './Gallery.module.css'

interface GalleryProps {
  images: ImageSet
  alt: string
  onAdvance?: (index: number) => void
  onZoom?: () => void
}

export function Gallery({ images, alt, onAdvance, onZoom }: GalleryProps) {
  const all = [images.detail, ...images.detail_gallery]
  const [active, setActive] = useState(0)
  const [lensPos, setLensPos] = useState({ x: 50, y: 50 })
  const zoomedRef = useRef(false)

  const activePath = all[active] ?? images.detail
  const zoomPath = active === 0 ? images.zoom : activePath

  function onMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    setLensPos({ x, y })
    if (!zoomedRef.current) {
      zoomedRef.current = true
      onZoom?.()
    }
  }

  function onMouseLeave() {
    zoomedRef.current = false
  }

  return (
    <div className={styles.wrap}>
      {all.length > 1 ? (
        <div className={styles.thumbs}>
          {all.map((path, i) => (
            <button
              key={path}
              className={[styles.thumb, i === active ? styles.active : ''].join(' ')}
              onClick={() => {
                setActive(i)
                onAdvance?.(i)
              }}
              aria-label={`Show image ${i + 1}`}
              aria-current={i === active}
            >
              <img src={mediaUrl(path)} alt="" />
            </button>
          ))}
        </div>
      ) : null}
      <div className={styles.mainFrame} onMouseMove={onMouseMove} onMouseLeave={onMouseLeave}>
        <img className={styles.mainImg} src={mediaUrl(activePath)} alt={alt} />
        <div
          className={styles.zoomLens}
          style={{
            backgroundImage: `url(${mediaUrl(zoomPath)})`,
            backgroundSize: '200%',
            backgroundPosition: `${lensPos.x}% ${lensPos.y}%`,
          }}
        />
      </div>
    </div>
  )
}
