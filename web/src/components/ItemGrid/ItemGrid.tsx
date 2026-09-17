import { SearchX } from 'lucide-react'
import type { ReactNode } from 'react'
import type { CatalogItem } from '../../lib/types'
import { ItemCard } from '../ItemCard/ItemCard'
import styles from './ItemGrid.module.css'

interface ItemGridProps {
  items: CatalogItem[] | null
  sponsoredIds?: Set<string>
  emptyHeading?: string
  emptyBody?: string
  emptyAction?: ReactNode
  skeletonCount?: number
}

export function ItemGrid({
  items,
  sponsoredIds,
  emptyHeading,
  emptyBody,
  emptyAction,
  skeletonCount = 12,
}: ItemGridProps) {
  if (items === null) {
    return (
      <div className={styles.grid} aria-busy="true" aria-label="Loading items">
        {Array.from({ length: skeletonCount }, (_, i) => (
          <div key={i} className={styles.skeletonCard}>
            <div className={[styles.skeletonBlock, styles.skeletonImage].join(' ')} />
            <div className={[styles.skeletonBlock, styles.skeletonLine].join(' ')} />
            <div className={[styles.skeletonBlock, styles.skeletonLineShort].join(' ')} />
          </div>
        ))}
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className={styles.grid}>
        <div className={styles.empty}>
          <SearchX className={styles.emptyIcon} size={28} strokeWidth={1.5} />
          {emptyHeading ? <h3 className={styles.emptyHeading}>{emptyHeading}</h3> : null}
          {emptyBody ? <p className={styles.emptyBody}>{emptyBody}</p> : null}
          {emptyAction}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.grid}>
      {items.map((item, i) => (
        <ItemCard
          key={item.item_id}
          item={item}
          sponsored={sponsoredIds?.has(item.item_id)}
          eagerImage={i < 4}
        />
      ))}
    </div>
  )
}
