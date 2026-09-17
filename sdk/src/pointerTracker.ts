import type { PointerBatchPayload } from './types'

/**
 * §7.2: "Sample with requestAnimationFrame over coalesced pointer
 * events. Flush every 250ms over WebSocket." Raw pointermove events are
 * buffered as they arrive; once per animation frame the buffer is
 * drained and each event's coalesced sub-samples (the sub-frame points
 * browsers batch internally) are extracted — recovering resolution rAF
 * alone would flatten to display refresh rate.
 */
export class PointerTracker {
  private points: { t: number; x: number; y: number; targetId: string | null }[] = []
  private rawBuffer: PointerEvent[] = []
  private rafId: number | null = null
  private flushTimer: ReturnType<typeof setInterval> | null = null
  private listening = false
  private getNow: () => number
  private onFlush: (payload: PointerBatchPayload) => void
  private flushIntervalMs: number

  constructor(getNow: () => number, onFlush: (payload: PointerBatchPayload) => void, flushIntervalMs: number) {
    this.getNow = getNow
    this.onFlush = onFlush
    this.flushIntervalMs = flushIntervalMs
  }

  start(): void {
    if (this.listening) return
    this.listening = true
    window.addEventListener('pointermove', this.handlePointerMove, { passive: true })
    this.scheduleFrame()
    this.flushTimer = setInterval(() => this.flush(), this.flushIntervalMs)
  }

  private handlePointerMove = (e: PointerEvent): void => {
    this.rawBuffer.push(e)
  }

  private scheduleFrame(): void {
    this.rafId = requestAnimationFrame(() => {
      this.drainFrame()
      if (this.listening) this.scheduleFrame()
    })
  }

  private drainFrame(): void {
    for (const e of this.rawBuffer) {
      const coalesced = typeof e.getCoalescedEvents === 'function' ? e.getCoalescedEvents() : []
      const samples = coalesced.length > 0 ? coalesced : [e]
      for (const s of samples) {
        const target = s.target as Element | null
        const targetId = target?.closest<HTMLElement>('[data-item-id]')?.dataset.itemId ?? null
        this.points.push({ t: this.getNow(), x: s.clientX, y: s.clientY, targetId })
      }
    }
    this.rawBuffer = []
  }

  private flush(): void {
    if (this.points.length === 0) return
    const t0 = this.points[0].t
    const dt: number[] = []
    const dx: number[] = []
    const dy: number[] = []
    const target_id: (string | null)[] = []
    let prevT = t0
    let prevX = this.points[0].x
    let prevY = this.points[0].y
    for (const p of this.points) {
      dt.push(p.t - prevT)
      dx.push(p.x - prevX)
      dy.push(p.y - prevY)
      target_id.push(p.targetId)
      prevT = p.t
      prevX = p.x
      prevY = p.y
    }
    this.onFlush({ t0, dt, dx, dy, target_id })
    this.points = []
  }

  stop(): void {
    this.listening = false
    window.removeEventListener('pointermove', this.handlePointerMove)
    if (this.rafId !== null) cancelAnimationFrame(this.rafId)
    if (this.flushTimer) clearInterval(this.flushTimer)
    this.drainFrame()
    this.flush()
  }
}
