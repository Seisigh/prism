import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ProductImage } from '../../components/ProductImage/ProductImage'
import { Price } from '../../components/Price/Price'
import { Rating } from '../../components/Rating/Rating'
import { compare, emptyStates } from '../../copy'
import { api } from '../../lib/api'
import type { CatalogItem } from '../../lib/types'
import styles from './Compare.module.css'

export function Compare() {
  const { setId = '' } = useParams()
  const [items, setItems] = useState<CatalogItem[] | null>(null)
  const [removed, setRemoved] = useState<Set<string>>(new Set())

  useEffect(() => {
    api
      .compare(setId)
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
  }, [setId])

  if (items === null) {
    return <div className={styles.page} aria-busy="true" />
  }

  const visible = items.filter((i) => !removed.has(i.item_id))

  if (visible.length < 2) {
    const category = visible[0]?.category ?? items[0]?.category ?? ''
    return (
      <div className={styles.page}>
        <div className={styles.emptyWrap}>
          <h1 className={styles.title}>{emptyStates.compareOneItem.heading}</h1>
          <p className={styles.subtitle}>{emptyStates.compareOneItem.body}</p>
          <Link to={`/category/${encodeURIComponent(category)}`} className={styles.removeBtn} style={{ color: 'var(--primary)' }}>
            {emptyStates.compareOneItem.action(category)}
          </Link>
        </div>
      </div>
    )
  }

  const rows: { label: string; render: (item: CatalogItem) => React.ReactNode }[] = [
    { label: '', render: (item) => <ProductImage path={item.images?.grid ?? null} alt={item.alt_text} /> },
    {
      label: 'Item',
      render: (item) => (
        <Link to={`/item/${item.item_id}`} style={{ fontWeight: 600 }}>
          {item.title}
        </Link>
      ),
    },
    { label: 'Brand', render: (item) => item.brand },
    { label: 'Price', render: (item) => <Price cents={item.price_cents} anchorCents={item.anchor_price_cents} /> },
    { label: 'Rating', render: (item) => <Rating value={item.rating} count={item.review_count} /> },
    { label: 'Stock', render: (item) => item.stock_label ?? 'In stock' },
    ...Array.from(new Set(items.flatMap((i) => Object.keys(i.spec))))
      .filter((key) => key !== 'Brand')
      .map((key) => ({
        label: key,
        render: (item: CatalogItem) => item.spec[key] ?? '—',
      })),
  ]

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>{compare.heading}</h1>
        <p className={styles.subtitle}>{compare.body}</p>
      </div>

      <div className={styles.table} style={{ gridTemplateColumns: `160px repeat(${visible.length}, 1fr)` }}>
        {rows.map((row, ri) => (
          <div className={styles.row} key={ri}>
            <div className={[styles.cell, styles.labelCell].join(' ')}>{row.label}</div>
            {visible.map((item) => (
              <div className={[styles.cell, styles.itemCell].join(' ')} key={item.item_id}>
                {ri === 0 && (
                  <button className={styles.removeBtn} onClick={() => setRemoved((s) => new Set(s).add(item.item_id))}>
                    {compare.remove}
                  </button>
                )}
                {row.render(item)}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
