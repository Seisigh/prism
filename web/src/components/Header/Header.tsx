import { Heart, MapPin, ShoppingCart, SlidersHorizontal, User } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { usePrismSDK } from '../../state/PrismSDKContext'
import { useCart } from '../../state/CartContext'
import { useWishlist } from '../../state/WishlistContext'
import { SearchBar } from '../SearchBar/SearchBar'
import styles from './Header.module.css'

export function Header({ onOpenProfile }: { onOpenProfile: () => void }) {
  const [categories, setCategories] = useState<string[]>([])
  const { count } = useCart()
  const { ids: wishlistIds } = useWishlist()
  const sdk = usePrismSDK()

  useEffect(() => {
    api
      .categories()
      .then((r) => setCategories(r.categories))
      .catch(() => setCategories([]))
  }, [])

  return (
    <header className={styles.header}>
      <div className={styles.topRow}>
        <Link to="/" className={styles.logoLink} aria-label="PRISM home">
          <svg width="132" height="25" viewBox="0 0 168 32" role="img" aria-label="PRISM">
            <g>
              <path d="M1 16 H11" stroke="#5A616E" strokeWidth="2" strokeLinecap="round" />
              <path d="M20.5 16 L31 10.5" stroke="#E8432F" strokeWidth="1.75" strokeLinecap="round" />
              <path d="M20.5 16 L31 14" stroke="#E88B2F" strokeWidth="1.75" strokeLinecap="round" />
              <path d="M20.5 16 L31 17.5" stroke="#3FA654" strokeWidth="1.75" strokeLinecap="round" />
              <path d="M20.5 16 L31 21" stroke="#3D8FDB" strokeWidth="1.75" strokeLinecap="round" />
              <path d="M16 5 L27 26 H5 Z" fill="none" stroke="#14161C" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            </g>
            <text x="44" y="22" fontFamily="Inter, sans-serif" fontSize="19" fontWeight={600} letterSpacing="3.4" fill="#14161C">
              PRISM
            </text>
          </svg>
        </Link>

        <div className={styles.location}>
          <span className={styles.locationLabel}>Deliver to</span>
          <span className={styles.locationValue}>
            <MapPin size={11} /> United States
          </span>
        </div>

        <SearchBar categories={categories} />

        <nav className={styles.actions} aria-label="Account">
          <button type="button" className={styles.actionBtn} onClick={onOpenProfile}>
            <SlidersHorizontal size={19} strokeWidth={1.75} />
            Profile
          </button>
          <div className={styles.actionBtn} aria-disabled="true">
            <User size={19} strokeWidth={1.75} />
            Account
          </div>
          <Link to="/cart" className={styles.actionBtn} aria-label={`Wishlist, ${wishlistIds.size} items`}>
            <Heart size={19} strokeWidth={1.75} fill={wishlistIds.size > 0 ? 'currentColor' : 'none'} />
            Saved
          </Link>
          <Link to="/cart" className={styles.actionBtn} aria-label={`Cart, ${count} items`}>
            <ShoppingCart size={19} strokeWidth={1.75} />
            Cart
            {count > 0 ? <span className={styles.cartCount}>{count}</span> : null}
          </Link>
        </nav>
      </div>

      <div className={styles.navStripOuter}>
        <nav className={styles.navStrip} aria-label="Categories">
          {categories.map((c) => (
            <NavLink
              key={c}
              to={`/category/${encodeURIComponent(c)}`}
              className={({ isActive }) => [styles.navLink, isActive ? styles.active : ''].join(' ')}
              onClick={() => sdk?.trackCategoryNavClick()}
            >
              {c}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
