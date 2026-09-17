import type {
  AutocompleteSuggestion,
  CatalogItem,
  ListResponse,
  Rail,
} from './types'

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`)
  return res.json() as Promise<T>
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
}

export function formatPrice(cents: number): { dollars: string; cents: string } {
  const dollars = Math.floor(cents / 100).toLocaleString('en-US')
  const centsPart = (cents % 100).toString().padStart(2, '0')
  return { dollars, cents: centsPart }
}
