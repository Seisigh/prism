import { FlaskConical, Heart, ShoppingCart } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '../../components/Button/Button'
import { Gallery } from '../../components/Gallery/Gallery'
import { ItemGrid } from '../../components/ItemGrid/ItemGrid'
import { Price } from '../../components/Price/Price'
import { Rating } from '../../components/Rating/Rating'
import { detail, reviewMarker } from '../../copy'
import { api } from '../../lib/api'
import type { CatalogItem, Rail } from '../../lib/types'
import { usePrismSDK } from '../../state/PrismSDKContext'
import { useActiveSeason } from '../../state/SeasonContext'
import { useCart } from '../../state/CartContext'
import { useWishlist } from '../../state/WishlistContext'
import { NotFound } from '../NotFound/NotFound'
import styles from './Detail.module.css'

const SEASON_LABELS: Record<string, string> = {
  spring: 'Spring',
  summer: 'Summer',
  fall: 'Fall',
  winter: 'Winter',
  holiday: 'Holiday',
}

export function Detail() {
  const { itemId = '' } = useParams()
  const [item, setItem] = useState<CatalogItem | null | 'not-found'>(null)
  const [alsoViewed, setAlsoViewed] = useState<Rail | null>(null)
  const [similar, setSimilar] = useState<Rail | null>(null)
  const [quantity, setQuantity] = useState(1)
  const { add } = useCart()
  const { has, toggle } = useWishlist()
  const sdk = usePrismSDK()
  const heroRef = useRef<HTMLDivElement>(null)
  const activeSeason = useActiveSeason()

  useEffect(() => {
    setItem(null)
    api
      .item(itemId)
      .then(setItem)
      .catch(() => setItem('not-found'))
    api.alsoViewed(itemId).then(setAlsoViewed).catch(() => setAlsoViewed(null))
    api.similar(itemId).then(setSimilar).catch(() => setSimilar(null))
  }, [itemId])

  useEffect(() => {
    if (!sdk || !itemId) return
    sdk.trackDetailViewStart(itemId)
    return () => sdk.trackDetailViewEnd(itemId)
  }, [sdk, itemId])

  // The one registerItemCard the product being looked at on its own page
  // never had: every other surface (grid/rail/compare/cart cards) feeds
  // the canonical view pipeline through this same registration, but the
  // detail page's own hero region never called it, so real detail-page
  // dwell has never produced a scored `item_view` — see STATE.md's
  // "Close-out pass" section. `getSurface()` (PrismSDKContext) already
  // resolves `/item/:id` to `"detail"`, and item_view.py's surface
  // precedence already ranks `"detail"` above grid/rail — this was the
  // missing data source, not a missing consumer. Depends on `item`
  // (not just `itemId`) so it only registers once the ref is actually
  // attached to a loaded item's hero element.
  useEffect(() => {
    if (!sdk || !heroRef.current || !item || item === 'not-found') return
    const el = heroRef.current
    sdk.registerItemCard(el, item.item_id)
    return () => sdk.unregisterItemCard(el)
  }, [sdk, item])

  useEffect(() => {
    if (!sdk) return
    for (const rail of [alsoViewed, similar]) {
      if (!rail) continue
      const slate = rail.items.map((i) => i.item_id)
      sdk.trackRecImpression(rail.rail_id, rail.policy_id, slate, slate.map(() => 1 / Math.max(slate.length, 1)))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sdk, alsoViewed, similar])

  if (item === 'not-found') return <NotFound />
  if (item === null) {
    return <div className={styles.page} aria-busy="true" />
  }

  const stockClass =
    item.stock_status === 'in_stock' ? styles.inStock : item.stock_status === 'low_stock' ? styles.low : styles.out
  const wishlisted = has(item.item_id)
  const showSeasonalBadge = item.season !== 'none' && item.season === activeSeason
  const ratingCounts = [5, 4, 3, 2, 1].map((star) => {
    // Deterministic distribution shaped around the item's rating, purely
    // for the histogram display — the review objects themselves are the
    // real synthetic content (see catalog/synth_attributes.py).
    const distance = Math.abs(item.rating - star)
    const weight = Math.max(0, 1 - distance / 3)
    return { star, pct: weight }
  })
  const totalWeight = ratingCounts.reduce((s, r) => s + r.pct, 0) || 1

  return (
    <div className={styles.page}>
      <div className={styles.breadcrumb}>
        <Link to="/">Home</Link> / <Link to={`/category/${encodeURIComponent(item.category)}`}>{item.category}</Link> / {item.title}
      </div>

      <div className={styles.layout}>
        <div ref={heroRef}>
          {item.images ? (
            <Gallery
              images={item.images}
              alt={item.alt_text}
              onZoom={() => sdk?.trackZoom(item.item_id)}
              onAdvance={(i) => sdk?.trackGalleryAdvance(item.item_id, i)}
            />
          ) : null}
        </div>

        <div className={styles.infoCol}>
          {item.badges[0] || showSeasonalBadge ? (
            <div className={styles.badgeRow}>
              {item.badges[0] ? <span className={styles.badge}>{item.badges[0]}</span> : null}
              {showSeasonalBadge ? <span className={styles.seasonalBadge}>{SEASON_LABELS[item.season]}</span> : null}
            </div>
          ) : null}
          <span className={styles.brand}>{item.brand}</span>
          <h1 className={styles.title}>{item.title}</h1>
          <Rating value={item.rating} count={item.review_count} size={14} />

          <div className={styles.priceBlock}>
            <Price cents={item.price_cents} anchorCents={item.anchor_price_cents} size="lg" />
          </div>
          <span className={styles.syntheticNotice}>
            <FlaskConical size={12} /> {detail.syntheticNotice}
          </span>

          <div className={styles.section} style={{ marginBottom: 0 }}>
            <h2 className={styles.sectionTitle} style={{ fontSize: 'var(--fs-16)' }}>
              {detail.aboutThisItem}
            </h2>
            <ul className={styles.bulletList}>
              {item.bullets.map((b, i) => (
                <li key={i} className={styles.bulletItem}>
                  <span className={styles.bulletDot}>&bull;</span>
                  {b}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className={styles.buyBox}>
          <Price cents={item.price_cents} anchorCents={item.anchor_price_cents} />
          <div className={styles.deliveryLine}>{item.shipping_line}</div>
          <div className={[styles.stockLine, stockClass].join(' ')}>
            {item.stock_status === 'in_stock' ? detail.inStock : item.stock_label}
          </div>

          {item.stock_status !== 'out_of_stock' && (
            <div className={styles.qtyRow}>
              <label htmlFor="qty" style={{ fontSize: 'var(--fs-14)', color: 'var(--slate)' }}>
                {detail.qty}
              </label>
              <select
                id="qty"
                className={styles.qtySelect}
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className={styles.buyBoxActions}>
            <Button
              variant="primary"
              disabled={item.stock_status === 'out_of_stock'}
              onClick={() => {
                add(item, quantity)
                sdk?.trackCartAdd(item.item_id, quantity)
              }}
            >
              <ShoppingCart size={16} /> {detail.addToCart}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                toggle(item.item_id)
                sdk?.trackWishlist(item.item_id, !wishlisted)
              }}
              aria-pressed={wishlisted}
            >
              <Heart size={16} fill={wishlisted ? 'currentColor' : 'none'} /> {detail.addToList}
            </Button>
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{detail.specifications}</h2>
        <table className={styles.specTable}>
          <tbody>
            {Object.entries(item.spec).map(([k, v]) => (
              <tr key={k} className={styles.specRow}>
                <td>{k}</td>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{detail.reviews}</h2>
        <div className={styles.reviewsLayout}>
          <div className={styles.histogram}>
            <div className={styles.histogramSummary}>
              <span className={styles.histogramSummaryValue}>{item.rating.toFixed(1)}</span>
              <Rating value={item.rating} count={item.review_count} showCount={false} size={16} />
            </div>
            {ratingCounts.map((r) => (
              <div key={r.star} className={styles.histogramRow}>
                <span>{r.star} star</span>
                <span className={styles.histogramTrack}>
                  <span
                    className={styles.histogramFill}
                    style={{ width: `${(r.pct / totalWeight) * 100}%`, display: 'block' }}
                  />
                </span>
                <span>{Math.round((r.pct / totalWeight) * 100)}%</span>
              </div>
            ))}
          </div>
          <div className={styles.reviewList}>
            {item.reviews.map((r, i) => (
              <div key={i} className={styles.reviewItem}>
                <div className={styles.reviewMeta}>
                  <Rating value={r.stars} count={0} showCount={false} size={12} />
                </div>
                <p className={styles.reviewBody}>{r.body}</p>
                <span className={styles.reviewSyntheticMarker}>{reviewMarker}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {alsoViewed && alsoViewed.items.length > 0 ? (
        <section className={styles.rail}>
          <h2 className={styles.railTitle}>{detail.alsoViewedTitle}</h2>
          <ItemGrid items={alsoViewed.items} skeletonCount={6} />
        </section>
      ) : null}

      {similar && similar.items.length > 0 ? (
        <section className={styles.rail}>
          <h2 className={styles.railTitle}>{detail.similarTitle}</h2>
          <ItemGrid items={similar.items} skeletonCount={6} />
        </section>
      ) : null}
    </div>
  )
}
