/**
 * Raw item visibility, straight off IntersectionObserver — deliberately
 * naive. This does NOT implement §8's merge-gap / 300ms-qualifying /
 * multi-surface-attribution rules; it just reports every 50%-threshold
 * crossing as a raw view_start/view_end pair. server/features/item_view.py
 * is the single canonical function that turns this raw stream into real
 * views (see that module's docstring) — duplicating its logic here would
 * be exactly the kind of second source of truth §8 exists to prevent.
 */

const VISIBILITY_THRESHOLD = 0.5

export interface ItemVisibilityCallbacks {
  onEnter: (itemId: string, t: number) => void
  onLeave: (itemId: string, t: number) => void
  onImpression: (itemId: string, t: number) => void
}

export class ItemVisibilityTracker {
  private observer: IntersectionObserver
  private above = new Set<string>()
  private impressed = new Set<string>()
  private elToItemId = new Map<Element, string>()
  private getNow: () => number
  private callbacks: ItemVisibilityCallbacks

  constructor(getNow: () => number, callbacks: ItemVisibilityCallbacks) {
    this.getNow = getNow
    this.callbacks = callbacks
    this.observer = new IntersectionObserver(this.handleEntries, {
      threshold: [0, VISIBILITY_THRESHOLD, 1],
    })
  }

  observe(el: Element, itemId: string): void {
    this.elToItemId.set(el, itemId)
    if (!this.impressed.has(itemId)) {
      this.impressed.add(itemId)
      this.callbacks.onImpression(itemId, this.getNow())
    }
    this.observer.observe(el)
  }

  unobserve(el: Element): void {
    const itemId = this.elToItemId.get(el)
    if (itemId && this.above.has(itemId)) {
      this.above.delete(itemId)
      this.callbacks.onLeave(itemId, this.getNow())
    }
    this.observer.unobserve(el)
    this.elToItemId.delete(el)
  }

  private handleEntries = (entries: IntersectionObserverEntry[]): void => {
    const t = this.getNow()
    for (const entry of entries) {
      const itemId = this.elToItemId.get(entry.target)
      if (!itemId) continue
      const isAbove = entry.intersectionRatio >= VISIBILITY_THRESHOLD
      const wasAbove = this.above.has(itemId)
      if (isAbove && !wasAbove) {
        this.above.add(itemId)
        this.callbacks.onEnter(itemId, t)
      } else if (!isAbove && wasAbove) {
        this.above.delete(itemId)
        this.callbacks.onLeave(itemId, t)
      }
    }
  }

  destroy(): void {
    this.observer.disconnect()
    this.above.clear()
    this.elToItemId.clear()
  }
}
