/**
 * Single source of truth for the telemetry envelope + event type list
 * (BUILD_BRIEF.md §7.1/§7.2). The "what gets recorded" page renders this
 * directly so the plain-language explanation can never drift out of sync
 * with what the SDK actually emits — the SDK (sdk/) imports the same
 * event type list rather than redeclaring it.
 */

export const ENVELOPE_FIELDS = [
  { field: 'event_id', description: 'Client-generated ID so the server can ignore a duplicate if the same event is sent twice.' },
  { field: 'session_id', description: 'A random code for this visit. Not tied to any account.' },
  { field: 'seq', description: 'Order of this event within the session.' },
  { field: 'ts_mono', description: "The browser's own clock, used to measure durations accurately." },
  { field: 'ts_wall', description: 'Wall-clock time, used only for the 90-day retention window.' },
  { field: 'demo', description: 'Whether the profile panel has been opened this session.' },
  { field: 'surface', description: 'Which part of the site: home, category, search, detail, compare, or cart.' },
  { field: 'mode', description: "The browsing mode PRISM inferred for this view: discovery, directed search, broad search, comparison, or refind." },
  { field: 'type', description: 'The kind of event — see the list below.' },
  { field: 'payload', description: 'The event-specific data (e.g. scroll position, which item, what was typed into search).' },
] as const

export const EVENT_TYPES = [
  { type: 'page_view', description: 'A page finished loading.' },
  { type: 'item_impression', description: "An item's card entered the screen." },
  { type: 'view_start', description: "An item's card became more than half visible for at least 300ms." },
  { type: 'view_end', description: 'That view closed (scrolled away, navigated, or the tab lost focus).' },
  { type: 'detail_view_start', description: 'A product detail page was opened.' },
  { type: 'detail_view_end', description: 'That detail page was left.' },
  { type: 'pointer_batch', description: 'A short batch of cursor positions, sampled about 60 times a second.' },
  { type: 'scroll_batch', description: 'A short batch of scroll positions.' },
  { type: 'hover_start', description: 'The cursor rested over something.' },
  { type: 'hover_end', description: 'The cursor left it.' },
  { type: 'click', description: 'A click or tap.' },
  { type: 'zoom', description: 'The product image was zoomed.' },
  { type: 'gallery_advance', description: 'The product gallery moved to another image.' },
  { type: 'panel_open', description: 'The profile panel was opened.' },
  { type: 'search', description: 'A search was submitted.' },
  { type: 'autocomplete_select', description: 'A search suggestion was chosen.' },
  { type: 'filter', description: 'A filter was applied or removed.' },
  { type: 'sort', description: 'The sort order was changed.' },
  { type: 'cart_add', description: 'An item was added to the cart.' },
  { type: 'cart_remove', description: 'An item was removed from the cart.' },
  { type: 'wishlist', description: 'An item was added to or removed from the wishlist.' },
  { type: 'checkout_start', description: 'The checkout stub was opened.' },
  { type: 'rec_impression', description: 'A recommendation rail was shown, including which policy chose it.' },
  { type: 'visibility_change', description: 'The browser tab was hidden or shown again.' },
  { type: 'session_end', description: 'The session ended (idle timeout, explicit end, or tab close).' },
] as const
