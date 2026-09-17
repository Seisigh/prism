import type { Mode, Surface } from './types'

/**
 * The "online" half of browsing-mode assignment (§4) — mirrors
 * server/features/mode.py's rules so the SDK can attach `mode` to each
 * envelope in real time. server/features/mode.py is the *offline* source
 * of truth, recomputed from the raw stored event log; §10.9's skew test
 * compares this online computation against that offline recomputation at
 * the same sealed checkpoints. Keep the two in sync by hand — there's no
 * shared runtime between Python and this package, so this is a deliberate
 * duplication, not an oversight.
 */

const QUERY_ACTIVE_WINDOW_MS = 180_000
const REFIND_MIN_GAP_MS = 60_000
const COMPARISON_WINDOW_MS = 120_000
const MODEL_TOKEN_RE = /^[a-z]{0,4}-?\d+[a-z0-9-]*$/i

interface ViewRecord {
  itemId: string
  start: number
  nearSubstituteSetId: string | null
}

interface QuerySubmission {
  submittedAt: number
  query: string
}

export class SessionModeTracker {
  private views: ViewRecord[] = []
  private activeQuery: QuerySubmission | null = null
  private categoryNavClickAt: number | null = null
  private brandTokens: Set<string>

  constructor(brandTokens: Iterable<string> = []) {
    this.brandTokens = new Set(Array.from(brandTokens, (b) => b.toLowerCase()))
  }

  setBrandTokens(tokens: Iterable<string>): void {
    this.brandTokens = new Set(Array.from(tokens, (b) => b.toLowerCase()))
  }

  recordQuerySubmission(t: number, query: string): void {
    this.activeQuery = { submittedAt: t, query }
    this.categoryNavClickAt = null
  }

  recordCategoryNavClick(t: number): void {
    this.categoryNavClickAt = t
  }

  /** Call once a view is confirmed open (crossed the 50% threshold for
   * 300ms) — mirrors item_view.py's "mode assigned at view open." */
  recordViewOpen(t: number, itemId: string, nearSubstituteSetId: string | null): void {
    this.views.push({ itemId, start: t, nearSubstituteSetId })
  }

  private isQueryActive(t: number): boolean {
    const q = this.activeQuery
    if (!q || t < q.submittedAt) return false
    if (t - q.submittedAt >= QUERY_ACTIVE_WINDOW_MS) return false
    if (this.categoryNavClickAt !== null && q.submittedAt <= this.categoryNavClickAt && this.categoryNavClickAt <= t) {
      return false
    }
    return true
  }

  private classifyQuery(query: string): 'directed' | 'broad' {
    const tokens = (query.toLowerCase().match(/[a-z0-9-]+/g) ?? []).filter(Boolean)
    if (tokens.length >= 3) return 'directed'
    if (tokens.some((t) => MODEL_TOKEN_RE.test(t))) return 'directed'
    if (tokens.some((t) => this.brandTokens.has(t))) return 'directed'
    return 'broad'
  }

  private isRefind(t: number, itemId: string): boolean {
    return this.views.some((v) => v.itemId === itemId && t - v.start >= REFIND_MIN_GAP_MS)
  }

  private isComparison(t: number, itemId: string, nearSubstituteSetId: string | null): boolean {
    if (nearSubstituteSetId === null) return false
    const windowStart = t - COMPARISON_WINDOW_MS
    return this.views.some(
      (v) =>
        v.nearSubstituteSetId === nearSubstituteSetId &&
        v.itemId !== itemId &&
        v.start >= windowStart &&
        v.start <= t,
    )
  }

  /** Precedence: refind > comparison > directed_search > broad_search >
   * discovery — identical ordering to server/features/mode.py::assign_mode. */
  assignMode(t: number, itemId: string, nearSubstituteSetId: string | null, _surface: Surface): Mode {
    if (this.isRefind(t, itemId)) return 'refind'
    if (this.isComparison(t, itemId, nearSubstituteSetId)) return 'comparison'
    if (this.isQueryActive(t)) {
      return this.classifyQuery(this.activeQuery!.query) === 'directed' ? 'directed_search' : 'broad_search'
    }
    return 'discovery'
  }
}
