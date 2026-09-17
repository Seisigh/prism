import { Check } from 'lucide-react'
import type { Facets } from '../../lib/types'
import styles from './FacetRail.module.css'

export interface FilterState {
  price_band?: string
  min_rating?: number
  in_stock_only?: boolean
}

interface FacetRailProps {
  facets: Facets | null
  filters: FilterState
  onChange: (next: FilterState) => void
}

export function FacetRail({ facets, filters, onChange }: FacetRailProps) {
  const hasFilters = Boolean(filters.price_band || filters.min_rating || filters.in_stock_only)

  return (
    <aside className={styles.rail} aria-label="Filters">
      <div className={styles.group}>
        <div className={styles.groupTitle}>Price</div>
        {(facets?.price_bands ?? []).map((band) => {
          const checked = filters.price_band === band.label
          return (
            <button
              key={band.label}
              className={styles.option}
              onClick={() => onChange({ ...filters, price_band: checked ? undefined : band.label })}
              aria-pressed={checked}
            >
              <span className={styles.optionLabel}>
                <span className={[styles.checkbox, checked ? styles.checked : ''].join(' ')}>
                  {checked ? <Check size={11} strokeWidth={3} /> : null}
                </span>
                {band.label}
              </span>
              <span className={styles.optionCount}>{band.count}</span>
            </button>
          )
        })}
      </div>

      <div className={styles.group}>
        <div className={styles.groupTitle}>Rating</div>
        {(facets?.ratings ?? []).map((r) => {
          const checked = filters.min_rating === r.min_rating
          return (
            <button
              key={r.min_rating}
              className={styles.option}
              onClick={() => onChange({ ...filters, min_rating: checked ? undefined : r.min_rating })}
              aria-pressed={checked}
            >
              <span className={styles.optionLabel}>
                <span className={[styles.checkbox, checked ? styles.checked : ''].join(' ')}>
                  {checked ? <Check size={11} strokeWidth={3} /> : null}
                </span>
                {r.min_rating.toFixed(1)}+ stars
              </span>
              <span className={styles.optionCount}>{r.count}</span>
            </button>
          )
        })}
      </div>

      <div className={styles.group}>
        <div className={styles.groupTitle}>Availability</div>
        <button
          className={styles.option}
          onClick={() => onChange({ ...filters, in_stock_only: !filters.in_stock_only })}
          aria-pressed={Boolean(filters.in_stock_only)}
        >
          <span className={styles.optionLabel}>
            <span className={[styles.checkbox, filters.in_stock_only ? styles.checked : ''].join(' ')}>
              {filters.in_stock_only ? <Check size={11} strokeWidth={3} /> : null}
            </span>
            In stock only
          </span>
        </button>
      </div>

      {hasFilters ? (
        <button className={styles.clearBtn} onClick={() => onChange({})}>
          Clear all filters
        </button>
      ) : null}
    </aside>
  )
}
