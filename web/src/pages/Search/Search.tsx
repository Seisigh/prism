import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { emptyStates } from '../../copy'
import { Button } from '../../components/Button/Button'
import { FacetRail, type FilterState } from '../../components/FacetRail/FacetRail'
import { ItemGrid } from '../../components/ItemGrid/ItemGrid'
import { api } from '../../lib/api'
import type { CatalogItem, Facets } from '../../lib/types'
import listing from '../../styles/listing.module.css'

export function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const [items, setItems] = useState<CatalogItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [facets, setFacets] = useState<Facets | null>(null)

  const filters: FilterState = {
    price_band: searchParams.get('price_band') ?? undefined,
    min_rating: searchParams.get('min_rating') ? Number(searchParams.get('min_rating')) : undefined,
    in_stock_only: searchParams.get('in_stock_only') === 'true' || undefined,
  }
  const sort = searchParams.get('sort') ?? ''

  useEffect(() => {
    setItems(null)
    const params = new URLSearchParams({ q: query })
    if (filters.price_band) params.set('price_band', filters.price_band)
    if (filters.min_rating) params.set('min_rating', String(filters.min_rating))
    if (filters.in_stock_only) params.set('in_stock_only', 'true')
    if (sort) params.set('sort', sort)
    api
      .search(params)
      .then((r) => {
        setItems(r.items)
        setTotal(r.total)
        setFacets(r.facets)
      })
      .catch(() => {
        setItems([])
        setTotal(0)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()])

  function updateFilters(next: FilterState) {
    const params = new URLSearchParams(searchParams)
    params.delete('price_band')
    params.delete('min_rating')
    params.delete('in_stock_only')
    if (next.price_band) params.set('price_band', next.price_band)
    if (next.min_rating) params.set('min_rating', String(next.min_rating))
    if (next.in_stock_only) params.set('in_stock_only', 'true')
    setSearchParams(params)
  }

  const sponsored = query.trim() ? (items ?? []).slice(0, 2) : []
  const organic = query.trim() ? (items ?? []).slice(2) : items
  const sponsoredIds = new Set(sponsored.map((i) => i.item_id))

  return (
    <div className={listing.page}>
      <FacetRail facets={facets} filters={filters} onChange={updateFilters} />
      <div className={listing.main}>
        {sponsored.length > 0 ? (
          <div className={listing.sponsoredStrip}>
            <span className={listing.sponsoredLabel}>Sponsored</span>
            <ItemGrid items={sponsored} sponsoredIds={sponsoredIds} skeletonCount={2} />
          </div>
        ) : null}
        <div className={listing.toolbar}>
          <h1 className={listing.title}>
            {query ? `Results for "${query}"` : 'All items'}
            {items ? <span className={listing.resultCount}>{total.toLocaleString('en-US')} items</span> : null}
          </h1>
          <select
            className={listing.sortSelect}
            value={sort || 'relevance'}
            onChange={(e) => {
              const params = new URLSearchParams(searchParams)
              if (e.target.value === 'relevance') params.delete('sort')
              else params.set('sort', e.target.value)
              setSearchParams(params)
            }}
            aria-label="Sort by"
          >
            <option value="relevance">Relevance</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
            <option value="rating">Avg. customer rating</option>
          </select>
        </div>
        <ItemGrid
          items={organic}
          emptyHeading={emptyStates.searchNoResults.heading(query)}
          emptyBody={emptyStates.searchNoResults.body}
          emptyAction={
            <Button variant="secondary" onClick={() => setSearchParams({ q: '' })}>
              {emptyStates.searchNoResults.action}
            </Button>
          }
        />
      </div>
    </div>
  )
}
