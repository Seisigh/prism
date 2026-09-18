import { ItemVisibilityTracker } from './itemVisibility'
import { SessionModeTracker } from './mode'
import { PointerTracker } from './pointerTracker'
import { ScrollTracker } from './scrollTracker'
import { Transport } from './transport'
import type { DeviceInfo, Envelope, EventType, Mode, ProfileUpdate, Surface } from './types'

export type { Envelope, EventType, Mode, Surface, DeviceInfo, ProfileUpdate } from './types'
export { SessionModeTracker } from './mode'

export interface PrismConfig {
  wsUrl: string
  httpUrl: string
  sessionId: string
  code: string
  brandTokens?: Iterable<string>
  getSurface: () => Surface
  /** Looks up an item's near-substitute-set id for comparison-mode
   * detection — the SDK doesn't have its own catalog copy, so the host
   * app supplies this from whatever it already fetched. */
  getNearSubstituteSetId?: (itemId: string) => string | null
}

const FLUSH_INTERVAL_MS = 250

function detectDeviceInfo(): DeviceInfo {
  const ua = navigator.userAgent
  const engineMatch = ua.match(/(Chrome|Firefox|Safari|Edg)\/([\d.]+)/)
  return {
    browser: engineMatch?.[1] ?? 'unknown',
    engine_version: engineMatch?.[2] ?? 'unknown',
    device_pixel_ratio: window.devicePixelRatio || 1,
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    pointer_type: window.matchMedia('(hover: none) and (pointer: coarse)').matches ? 'touch' : 'mouse',
  }
}

/**
 * The framework-agnostic PRISM telemetry client (§3: "sdk/ browser
 * telemetry package (TypeScript, framework-agnostic)"). Never constructed
 * or `.init()`-ed before consent is accepted — the host app (web/) owns
 * that gate; this class assumes it's already been cleared.
 */
export class PrismSDK {
  private transport: Transport
  private modeTracker: SessionModeTracker
  private itemVisibility: ItemVisibilityTracker
  private pointerTracker: PointerTracker
  private scrollTracker: ScrollTracker
  private seq = 0
  private demo = false
  private device: DeviceInfo
  private hoverStarts = new Map<Element, string>()
  private config: PrismConfig
  private trackedImpressions = new Set<string>()
  private profileUpdateListeners = new Set<(update: ProfileUpdate) => void>()

  constructor(config: PrismConfig) {
    this.config = config
    this.device = detectDeviceInfo()
    this.transport = new Transport({
      wsUrl: config.wsUrl,
      httpUrl: config.httpUrl,
      sessionId: config.sessionId,
      code: config.code,
    })
    this.modeTracker = new SessionModeTracker(config.brandTokens ?? [])
    this.itemVisibility = new ItemVisibilityTracker(this.now, {
      onImpression: (itemId, t) => this.emit('item_impression', { item_id: itemId }, t),
      onEnter: (itemId, t) => {
        const setId = this.config.getNearSubstituteSetId?.(itemId) ?? null
        const mode = this.modeTracker.assignMode(t, itemId, setId, this.config.getSurface())
        this.modeTracker.recordViewOpen(t, itemId, setId)
        this.emit('view_start', { item_id: itemId }, t, mode)
      },
      onLeave: (itemId, t) => this.emit('view_end', { item_id: itemId }, t),
    })
    this.pointerTracker = new PointerTracker(this.now, (payload) => this.emit('pointer_batch', { ...payload }), FLUSH_INTERVAL_MS)
    this.scrollTracker = new ScrollTracker(this.now, (payload) => this.emit('scroll_batch', { ...payload }), FLUSH_INTERVAL_MS)
  }

  private now = (): number => performance.now()

  private emit(type: EventType, payload: object, t?: number, mode?: Mode | null): void {
    const envelope: Envelope = {
      event_id: crypto.randomUUID(),
      session_id: this.config.sessionId,
      seq: this.seq++,
      ts_mono: t ?? this.now(),
      ts_wall: Date.now(),
      demo: this.demo,
      surface: this.config.getSurface(),
      mode: mode ?? null,
      type,
      payload: payload as Record<string, unknown>,
    }
    this.transport.enqueue(envelope)
  }

  init(): void {
    this.transport.connect({
      onMessage: (data) => {
        const message = data as { type?: string }
        if (message?.type === 'profile_update') {
          this.profileUpdateListeners.forEach((listener) => listener(data as ProfileUpdate))
        }
      },
    })
    this.pointerTracker.start()
    this.scrollTracker.start()
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
    this.emit('page_view', { path: location.pathname, device: this.device })
  }

  private handleVisibilityChange = (): void => {
    this.emit('visibility_change', { hidden: document.hidden })
  }

  // --- Public tracking API for discrete, app-triggered events ---------

  setDemo(demo: boolean): void {
    this.demo = demo
  }

  registerItemCard(el: Element, itemId: string): void {
    el.setAttribute('data-item-id', itemId)
    this.itemVisibility.observe(el, itemId)
  }

  unregisterItemCard(el: Element): void {
    this.itemVisibility.unobserve(el)
  }

  trackHoverStart(el: Element, itemId: string): void {
    this.hoverStarts.set(el, itemId)
    this.emit('hover_start', { item_id: itemId })
  }

  trackHoverEnd(el: Element): void {
    const itemId = this.hoverStarts.get(el)
    if (!itemId) return
    this.hoverStarts.delete(el)
    this.emit('hover_end', { item_id: itemId })
  }

  trackClick(payload: Record<string, unknown>): void {
    this.emit('click', payload)
  }

  trackDetailViewStart(itemId: string): void {
    const setId = this.config.getNearSubstituteSetId?.(itemId) ?? null
    const mode = this.modeTracker.assignMode(this.now(), itemId, setId, this.config.getSurface())
    this.modeTracker.recordViewOpen(this.now(), itemId, setId)
    this.emit('detail_view_start', { item_id: itemId }, undefined, mode)
  }

  trackDetailViewEnd(itemId: string): void {
    this.emit('detail_view_end', { item_id: itemId })
  }

  trackZoom(itemId: string): void {
    this.emit('zoom', { item_id: itemId })
  }

  trackGalleryAdvance(itemId: string, index: number): void {
    this.emit('gallery_advance', { item_id: itemId, index })
  }

  trackPanelOpen(): void {
    this.emit('panel_open', {})
  }

  trackSearch(query: string): void {
    this.modeTracker.recordQuerySubmission(this.now(), query)
    this.emit('search', { query })
  }

  trackAutocompleteSelect(itemId: string, query: string): void {
    this.emit('autocomplete_select', { item_id: itemId, query })
  }

  trackFilter(payload: object): void {
    this.emit('filter', payload)
  }

  trackSort(sort: string): void {
    this.emit('sort', { sort })
  }

  trackCartAdd(itemId: string, quantity: number): void {
    this.emit('cart_add', { item_id: itemId, quantity })
  }

  trackCartRemove(itemId: string): void {
    this.emit('cart_remove', { item_id: itemId })
  }

  trackWishlist(itemId: string, added: boolean): void {
    this.emit('wishlist', { item_id: itemId, added })
  }

  trackCheckoutStart(): void {
    this.emit('checkout_start', {})
  }

  trackRecImpression(railId: string, policyId: string, slate: string[], propensities: number[], modelVersion: string | null = null): void {
    // React effect double-invocation (StrictMode, dev only) can call this
    // twice with an identical slate for the same rail — dedupe on
    // (railId, slate) rather than firing a duplicate impression. A
    // genuinely refreshed rail (different slate) still tracks normally.
    const key = `${railId}:${slate.join(',')}`
    if (this.trackedImpressions.has(key)) return
    this.trackedImpressions.add(key)
    this.emit('rec_impression', { rail_id: railId, policy_id: policyId, model_version: modelVersion, slate, propensities })
  }

  trackCategoryNavClick(): void {
    this.modeTracker.recordCategoryNavClick(this.now())
  }

  /** Registers a listener for live profile-update pushes (§12). Returns
   * an unsubscribe function so React effects can clean up on unmount. */
  onProfileUpdate(listener: (update: ProfileUpdate) => void): () => void {
    this.profileUpdateListeners.add(listener)
    return () => this.profileUpdateListeners.delete(listener)
  }

  destroy(): void {
    this.emit('session_end', {})
    this.pointerTracker.stop()
    this.scrollTracker.stop()
    this.itemVisibility.destroy()
    document.removeEventListener('visibilitychange', this.handleVisibilityChange)
    this.transport.destroy()
  }
}
