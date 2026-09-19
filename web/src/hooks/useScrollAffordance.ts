import { useCallback, useEffect, useRef, useState } from 'react'

// How far an arrow click scrolls, as a fraction of the container's own
// visible width -- a "page" of content at a time, not the whole list.
const ARROW_SCROLL_FRACTION = 0.8

// Single source of truth for "this element scrolls horizontally, and a
// viewer needs to be able to tell and reach the rest of it": tracks
// scroll position so callers can show arrows/fade only on the edge that
// actually has more content, and redirects an ordinary vertical mouse
// wheel to horizontal scroll (most visitors have a wheel, not a
// trackpad, and shift+wheel is not a discoverable gesture).
export function useScrollAffordance<T extends HTMLElement>(
  deps: readonly unknown[] = [],
  options: { wheelRedirect?: boolean } = {},
) {
  // Off for a container whose primary scroll axis is already vertical
  // (SessionViewer's event log scrolls itself, independent of the page)
  // -- redirecting its vertical wheel input to horizontal would hijack
  // the scroll a viewer actually wants.
  const { wheelRedirect = true } = options
  const ref = useRef<T>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)

  const updateScrollState = useCallback(() => {
    const el = ref.current
    if (!el) return
    // 1px slop -- fractional scroll positions (high-DPI displays,
    // smooth-scroll momentum) can leave scrollLeft a hair short of the
    // true max, which would otherwise leave the trailing arrow/fade
    // stuck visible forever at the "end" of the content.
    setCanScrollLeft(el.scrollLeft > 1)
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    updateScrollState()
    el.addEventListener('scroll', updateScrollState, { passive: true })
    const observer = new ResizeObserver(updateScrollState)
    observer.observe(el)
    window.addEventListener('resize', updateScrollState)
    return () => {
      el.removeEventListener('scroll', updateScrollState)
      observer.disconnect()
      window.removeEventListener('resize', updateScrollState)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [updateScrollState, ...deps])

  // React attaches its own onWheel prop as a passive listener (wheel and
  // touch listeners are passive by default since React 17), so
  // preventDefault() inside a JSX onWheel handler is silently a no-op --
  // confirmed live, it throws "Unable to preventDefault inside passive
  // event listener invocation" in the console and never actually stops
  // the page from also scrolling vertically underneath the redirected
  // horizontal scroll. A native listener registered with
  // { passive: false } is the only way to make preventDefault real here.
  useEffect(() => {
    if (!wheelRedirect) return
    const el = ref.current
    if (!el) return
    function handleWheel(e: WheelEvent) {
      if (!el) return
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        el.scrollLeft += e.deltaY
        e.preventDefault()
      }
    }
    el.addEventListener('wheel', handleWheel, { passive: false })
    return () => el.removeEventListener('wheel', handleWheel)
  }, [wheelRedirect])

  const scrollByArrow = useCallback((direction: 1 | -1) => {
    const el = ref.current
    if (!el) return
    el.scrollBy({ left: direction * el.clientWidth * ARROW_SCROLL_FRACTION, behavior: 'smooth' })
  }, [])

  return { ref, canScrollLeft, canScrollRight, scrollByArrow, updateScrollState }
}
