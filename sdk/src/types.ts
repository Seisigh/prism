/**
 * The telemetry envelope (BUILD_BRIEF.md §7.1) and event type list
 * (§7.2). Mirrors server/ingest/envelope.py field-for-field — if these
 * two drift, ingest starts silently dropping envelopes as malformed.
 */

export type Surface = 'home' | 'category' | 'search' | 'detail' | 'compare' | 'cart'

export type Mode = 'discovery' | 'directed_search' | 'broad_search' | 'comparison' | 'refind'

export type EventType =
  | 'page_view'
  | 'item_impression'
  | 'view_start'
  | 'view_end'
  | 'detail_view_start'
  | 'detail_view_end'
  | 'pointer_batch'
  | 'scroll_batch'
  | 'hover_start'
  | 'hover_end'
  | 'click'
  | 'zoom'
  | 'gallery_advance'
  | 'panel_open'
  | 'search'
  | 'autocomplete_select'
  | 'filter'
  | 'sort'
  | 'cart_add'
  | 'cart_remove'
  | 'wishlist'
  | 'checkout_start'
  | 'rec_impression'
  | 'visibility_change'
  | 'session_end'

export interface Envelope {
  event_id: string
  session_id: string
  seq: number
  ts_mono: number
  ts_wall: number
  demo: boolean
  surface: Surface
  mode: Mode | null
  type: EventType
  payload: Record<string, unknown>
}

/** §7.2: delta-encoded pointer batch. `t0` is the batch's start time;
 * `dt[i]` is the gap since the previous sample (dt[0] is since t0). */
export interface PointerBatchPayload {
  t0: number
  dt: number[]
  dx: number[]
  dy: number[]
  target_id: (string | null)[]
}

export interface ScrollBatchPayload {
  t0: number
  dt: number[]
  y_ratio: number[]
}

export interface RecImpressionPayload {
  rail_id: string
  policy_id: string
  model_version: string | null
  slate: string[]
  propensities: number[]
}

export interface DeviceInfo {
  browser: string
  engine_version: string
  device_pixel_ratio: number
  viewport_width: number
  viewport_height: number
  pointer_type: 'mouse' | 'touch' | 'pen'
}
