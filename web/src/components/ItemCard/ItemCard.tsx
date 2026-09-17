import { Heart } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CatalogItem } from '../../lib/types'
import { useWishlist } from '../../state/WishlistContext'
import { Price } from '../Price/Price'
import { ProductImage } from '../ProductImage/ProductImage'
import { Rating } from '../Rating/Rating'
import styles from './ItemCard.module.css'

interface ItemCardProps {
  item: CatalogItem
  sponsored?: boolean
  eagerImage?: boolean
}

export function ItemCard({ item, sponsored = false, eagerImage = false }: ItemCardProps) {
  const { has, toggle } = useWishlist()
  const wishlisted = has(item.item_id)

  return (
    <article className={styles.card} data-item-id={item.item_id}>
      <div className={styles.imageWrap}>
        {item.badges[0] ? <span className={styles.badge}>{item.badges[0]}</span> : null}
        {sponsored ? <span className={styles.sponsored}>Sponsored</span> : null}
        <button
          type="button"
          className={[styles.wishlistBtn, wishlisted ? styles.active : ''].join(' ')}
          onClick={(e) => {
            e.preventDefault()
            toggle(item.item_id)
          }}
          aria-pressed={wishlisted}
          aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
        >
          <Heart size={14} fill={wishlisted ? 'currentColor' : 'none'} strokeWidth={2} />
        </button>
        <Link to={`/item/${item.item_id}`} tabIndex={-1}>
          <ProductImage path={item.images?.grid ?? null} alt={item.alt_text} eager={eagerImage} />
        </Link>
      </div>

      <Link to={`/item/${item.item_id}`} className={styles.title}>
        {item.title}
      </Link>
      <span className={styles.brand}>{item.brand}</span>

      <Rating value={item.rating} count={item.review_count} />

      <div className={styles.spacer} />

      <div className={styles.priceRow}>
        <Price cents={item.price_cents} anchorCents={item.anchor_price_cents} />
      </div>

      {item.stock_status !== 'in_stock' && item.stock_label ? (
        <span className={[styles.stockLabel, item.stock_status === 'low_stock' ? styles.low : styles.out].join(' ')}>
          {item.stock_label}
        </span>
      ) : (
        <span className={styles.shipping}>{item.shipping_line}</span>
      )}
    </article>
  )
}
