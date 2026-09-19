import type { ReactNode } from 'react'
import { useScrollAffordance } from '../../hooks/useScrollAffordance'
import { ScrollArrows } from '../ScrollArrows/ScrollArrows'

// Wraps a wide table (or any horizontally-overflowing block) with the
// same scroll affordance as the storefront category strip: fade masks
// gated on real scroll position, arrows, wheel-redirect, keyboard focus.
// `outerClassName` must compose scrollFade.module.css's `.fadeOuter`;
// `scrollClassName` is the element that actually gets `overflow-x: auto`.
export function ScrollableRegion({
  outerClassName,
  scrollClassName,
  ariaLabel,
  children,
  arrows = false,
  wheelRedirect = true,
}: {
  outerClassName: string
  scrollClassName: string
  ariaLabel: string
  children: ReactNode
  // Off by default: these regions wrap tables that scroll with the
  // page vertically (no internal height limit), so the outer wrapper
  // can be page-length. An arrow is `position: absolute; top: 0;
  // bottom: 0`, sized to that wrapper -- on a 98-row table that's a
  // ~4000px-tall button whose icon (grid-centered) lands nowhere near
  // the visible viewport slice, found live while verifying this at
  // 768px. Fade doesn't have this problem (it's correct at every
  // scroll position, not a single fixed click target), so it's the
  // affordance these get. Only turn arrows on for a region that's
  // genuinely short/fixed-height, where top: 0/bottom: 0 spans a
  // sensible, always-visible size (see Header/AdminLayout's own direct
  // useScrollAffordance + ScrollArrows wiring for that case).
  arrows?: boolean
  // Off for a container that's primarily vertically scrollable in its
  // own right (SessionViewer's event log) -- redirecting the wheel
  // would hijack the scroll a viewer actually wants there.
  wheelRedirect?: boolean
}) {
  const { ref, canScrollLeft, canScrollRight, scrollByArrow } = useScrollAffordance<HTMLDivElement>([], { wheelRedirect })

  return (
    <div className={outerClassName} data-scroll-left={canScrollLeft} data-scroll-right={canScrollRight}>
      {arrows ? (
        <ScrollArrows
          canScrollLeft={canScrollLeft}
          canScrollRight={canScrollRight}
          onScrollLeft={() => scrollByArrow(-1)}
          onScrollRight={() => scrollByArrow(1)}
          ariaLabelPrefix={`Scroll ${ariaLabel}`}
        />
      ) : null}
      <div ref={ref} className={scrollClassName} tabIndex={0} aria-label={ariaLabel}>
        {children}
      </div>
    </div>
  )
}
