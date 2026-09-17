import type {
  AutocompleteSuggestion,
  CatalogItem,
  ListResponse,
  Rail,
} from './types'

// Populated as CatalogItem-shaped objects pass through getJSON, so the
// SDK's getNearSubstituteSetId lookup (comparison-mode detection, §4.1)
// has something to read without a second round-trip or a full catalog
// copy living in the SDK itself.
const itemMetadataCache = new Map<string, { near_substitute_set_id: string | null }>()

export function getCachedNearSubstituteSetId(itemId: string): string | null {
  return itemMetadataCache.get(itemId)?.near_substitute_set_id ?? null
}

function cacheItemMetadata(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(cacheItemMetadata)
    return
  }
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if (typeof obj.item_id === 'string' && 'near_substitute_set_id' in obj) {
      itemMetadataCache.set(obj.item_id, { near_substitute_set_id: (obj.near_substitute_set_id as string | null) ?? null })
    }
    Object.values(obj).forEach(cacheItemMetadata)
  }
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`)
  const data = (await res.json()) as T
  cacheItemMetadata(data)
  return data
}

export function mediaUrl(path: string): string {
  return `/media/thumbs/${path}`
}

export const api = {
  home: () => getJSON<{ categories: string[]; rails: Rail[] }>('/api/home'),
  categories: () => getJSON<{ categories: string[] }>('/api/categories'),
  item: (itemId: string) => getJSON<CatalogItem>(`/api/items/${itemId}`),
  similar: (itemId: string) => getJSON<Rail>(`/api/items/${itemId}/similar`),
  alsoViewed: (itemId: string) => getJSON<Rail>(`/api/items/${itemId}/also-viewed`),
  compare: (setId: string) => getJSON<{ near_substitute_set_id: string; items: CatalogItem[] }>(`/api/compare/${setId}`),
  category: (category: string, params: URLSearchParams) =>
    getJSON<ListResponse>(`/api/category/${encodeURIComponent(category)}?${params.toString()}`),
  search: (params: URLSearchParams) => getJSON<ListResponse & { query: string }>(`/api/search?${params.toString()}`),
  autocomplete: (q: string) =>
    getJSON<{ suggestions: AutocompleteSuggestion[] }>(`/api/autocomplete?q=${encodeURIComponent(q)}`),
  brandTokens: () => getJSON<{ tokens: string[] }>('/api/brand-tokens'),
}

export function formatPrice(cents: number): { dollars: string; cents: string } {
  const dollars = Math.floor(cents / 100).toLocaleString('en-US')
  const centsPart = (cents % 100).toString().padStart(2, '0')
  return { dollars, cents: centsPart }
}
