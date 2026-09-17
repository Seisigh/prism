import type { ScrollBatchPayload } from './types'

/** Scroll position as a 0..1 ratio of scrollable depth, batched the same
 * way as pointer samples (§7.2's `scroll_batch`). */
export class ScrollTracker {
  private points: { t: number; ratio: number }[] = []
  private flushTimer: ReturnType<typeof setInterval> | null = null
  private listening = false
  private getNow: () => number
  private onFlush: (payload: ScrollBatchPayload) => void
  private flushIntervalMs: number

  constructor(getNow: () => number, onFlush: (payload: ScrollBatchPayload) => void, flushIntervalMs: number) {
    this.getNow = getNow
    this.onFlush = onFlush
    this.flushIntervalMs = flushIntervalMs
  }

  start(): void {
    if (this.listening) return
    this.listening = true
    window.addEventListener('scroll', this.handleScroll, { passive: true })
    this.handleScroll()
    this.flushTimer = setInterval(() => this.flush(), this.flushIntervalMs)
  }

  private handleScroll = (): void => {
    const doc = document.documentElement
    const scrollable = doc.scrollHeight - doc.clientHeight
    const ratio = scrollable > 0 ? Math.min(1, Math.max(0, window.scrollY / scrollable)) : 0
    this.points.push({ t: this.getNow(), ratio })
  }

  private flush(): void {
    if (this.points.length === 0) return
    const t0 = this.points[0].t
    const dt: number[] = []
    const y_ratio: number[] = []
    let prevT = t0
    for (const p of this.points) {
      dt.push(p.t - prevT)
      y_ratio.push(p.ratio)
      prevT = p.t
    }
    this.onFlush({ t0, dt, y_ratio })
    this.points = []
  }

  stop(): void {
    this.listening = false
    window.removeEventListener('scroll', this.handleScroll)
    if (this.flushTimer) clearInterval(this.flushTimer)
    this.flush()
  }
}
