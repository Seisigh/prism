import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type HTMLAttributes,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
  type TouchEvent,
} from 'react'
import { createPortal } from 'react-dom'
import styles from './Tooltip.module.css'

const SHOW_DELAY_MS = 200
const VIEWPORT_MARGIN = 8
const TRIGGER_GAP = 8

// Wraps a single trigger element (the signal name, the column header
// text -- never a whole card or cell, so raw/normalized values next to
// it stay selectable and copyable) and renders the bubble through a
// portal to document.body. A tooltip nested inside a clipping container
// (overflow: hidden on a card, overflow-x: auto on a table) gets cut by
// exactly the rules the scroll-affordance audit covered, so it can't
// live in the DOM tree it describes.
export function Tooltip({ content, children }: { content: ReactNode; children: ReactElement<HTMLAttributes<HTMLElement>> }) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const showTimer = useRef<number | null>(null)
  const triggerRef = useRef<HTMLElement | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const isTouch = useRef(false)
  const id = useId()

  function clearShowTimer() {
    if (showTimer.current !== null) {
      window.clearTimeout(showTimer.current)
      showTimer.current = null
    }
  }

  function scheduleShow() {
    clearShowTimer()
    showTimer.current = window.setTimeout(() => setVisible(true), SHOW_DELAY_MS)
  }

  function hide() {
    clearShowTimer()
    setVisible(false)
  }

  useEffect(() => {
    if (!visible) return undefined
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') hide()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visible])

  // Positioned in an effect, not inline, because the flip/clamp decision
  // needs the bubble's own rendered size -- it's measured with
  // visibility: hidden on the first frame, then placed for real.
  useEffect(() => {
    if (!visible) return undefined
    function updatePosition() {
      const trigger = triggerRef.current
      if (!trigger) return
      const rect = trigger.getBoundingClientRect()
      const tooltipRect = tooltipRef.current?.getBoundingClientRect()
      const tooltipHeight = tooltipRect?.height ?? 0
      const tooltipWidth = tooltipRect?.width ?? 240

      let top = rect.bottom + TRIGGER_GAP
      const fitsBelow = top + tooltipHeight <= window.innerHeight - VIEWPORT_MARGIN
      const fitsAbove = rect.top - TRIGGER_GAP - tooltipHeight >= VIEWPORT_MARGIN
      if (!fitsBelow && fitsAbove) {
        top = rect.top - TRIGGER_GAP - tooltipHeight
      }

      let left = rect.left
      if (left + tooltipWidth > window.innerWidth - VIEWPORT_MARGIN) {
        left = window.innerWidth - VIEWPORT_MARGIN - tooltipWidth
      }
      left = Math.max(VIEWPORT_MARGIN, left)

      setCoords({ top, left })
    }
    updatePosition()
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
    return () => {
      window.removeEventListener('scroll', updatePosition, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [visible])

  if (!isValidElement(children)) return children

  const trigger = cloneElement(children, {
    ref: (el: HTMLElement | null) => {
      triggerRef.current = el
    },
    'aria-describedby': visible ? id : undefined,
    onMouseEnter: (e: MouseEvent<HTMLElement>) => {
      children.props.onMouseEnter?.(e)
      if (isTouch.current) return
      scheduleShow()
    },
    onMouseLeave: (e: MouseEvent<HTMLElement>) => {
      children.props.onMouseLeave?.(e)
      if (isTouch.current) return
      hide()
    },
    onFocus: (e: FocusEvent<HTMLElement>) => {
      children.props.onFocus?.(e)
      if (isTouch.current) return
      scheduleShow()
    },
    onBlur: (e: FocusEvent<HTMLElement>) => {
      children.props.onBlur?.(e)
      if (isTouch.current) return
      hide()
    },
    onTouchStart: (e: TouchEvent<HTMLElement>) => {
      children.props.onTouchStart?.(e)
      isTouch.current = true
    },
    onClick: (e: MouseEvent<HTMLElement>) => {
      children.props.onClick?.(e)
      if (!isTouch.current) return
      setVisible((v) => !v)
    },
  } as HTMLAttributes<HTMLElement>)

  return (
    <>
      {trigger}
      {visible
        ? createPortal(
            <div
              ref={tooltipRef}
              role="tooltip"
              id={id}
              className={styles.tooltip}
              style={coords ? { top: coords.top, left: coords.left } : { top: 0, left: 0, visibility: 'hidden' }}
            >
              {content}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
