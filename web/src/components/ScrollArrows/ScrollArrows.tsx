import { ChevronLeft, ChevronRight } from 'lucide-react'
import styles from './ScrollArrows.module.css'

// Paired with useScrollAffordance and a container that composes
// scrollFade.module.css's .fadeOuter -- see Header.module.css for the
// reference wiring. Rendered only for the edge that actually has more
// content, so an already-scrolled-to-the-end container doesn't keep
// implying there's more.
export function ScrollArrows({
  canScrollLeft,
  canScrollRight,
  onScrollLeft,
  onScrollRight,
  ariaLabelPrefix = 'Scroll',
}: {
  canScrollLeft: boolean
  canScrollRight: boolean
  onScrollLeft: () => void
  onScrollRight: () => void
  ariaLabelPrefix?: string
}) {
  return (
    <>
      {canScrollLeft ? (
        <button
          type="button"
          className={[styles.arrow, styles.arrowLeft].join(' ')}
          onClick={onScrollLeft}
          aria-label={`${ariaLabelPrefix} left`}
        >
          <ChevronLeft size={16} />
        </button>
      ) : null}
      {canScrollRight ? (
        <button
          type="button"
          className={[styles.arrow, styles.arrowRight].join(' ')}
          onClick={onScrollRight}
          aria-label={`${ariaLabelPrefix} right`}
        >
          <ChevronRight size={16} />
        </button>
      ) : null}
    </>
  )
}
