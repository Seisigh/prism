import { Star } from 'lucide-react'
import styles from './Rating.module.css'

interface RatingProps {
  value: number
  count: number
  size?: number
  showCount?: boolean
}

export function Rating({ value, count, size = 12, showCount = true }: RatingProps) {
  const pct = Math.max(0, Math.min(1, value / 5)) * 100
  return (
    <span className={styles.rating}>
      <span className={styles.stars} style={{ width: size * 5 + 4 * 4 }} aria-hidden="true">
        <StarRow size={size} />
        <span className={styles.starsFill} style={{ width: `${pct}%` }}>
          <StarRow size={size} filled />
        </span>
      </span>
      <span className={styles.value}>{value.toFixed(1)}</span>
      {showCount ? (
        <span className={styles.count}>({count.toLocaleString('en-US')})</span>
      ) : null}
      <span className="visually-hidden">
        {showCount ? `${value.toFixed(1)} out of 5 stars, ${count} reviews` : `${value.toFixed(1)} out of 5 stars`}
      </span>
    </span>
  )
}

function StarRow({ size, filled = false }: { size: number; filled?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star key={i} size={size} fill={filled ? 'currentColor' : 'none'} strokeWidth={filled ? 0 : 1.5} />
      ))}
    </span>
  )
}
