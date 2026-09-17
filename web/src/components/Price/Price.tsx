import { formatPrice } from '../../lib/api'
import styles from './Price.module.css'

interface PriceProps {
  cents: number
  anchorCents?: number | null
  size?: 'md' | 'lg'
  showSavings?: boolean
}

export function Price({ cents, anchorCents, size = 'md', showSavings = true }: PriceProps) {
  const { dollars, cents: centsPart } = formatPrice(cents)
  const fontSize = size === 'lg' ? 'var(--fs-32)' : 'var(--fs-20)'
  const discountPct = anchorCents && anchorCents > cents ? Math.round((1 - cents / anchorCents) * 100) : null

  return (
    <span className={styles.price} style={{ fontSize }}>
      <span className={styles.symbol}>$</span>
      <span className={styles.dollars}>{dollars}</span>
      <sup className={styles.cents}>{centsPart}</sup>
      {anchorCents ? (
        <span className={styles.anchor}>
          ${(anchorCents / 100).toFixed(2)}
        </span>
      ) : null}
      {discountPct && showSavings ? <span className={styles.savings}>Save {discountPct}%</span> : null}
    </span>
  )
}
