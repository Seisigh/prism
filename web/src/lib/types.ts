export interface ImageSet {
  grid: string
  detail: string
  zoom: string
  detail_gallery: string[]
}

export interface ReviewSnippet {
  stars: number
  body: string
  synthetic: boolean
}

export interface CatalogItem {
  item_id: string
  title: string
  category: string
  verticals: string[]
  gender: 'womens' | 'mens' | 'unisex'
  age_band: 'kids' | 'teen' | 'adult' | 'older_adult'
  brand: string
  brand_tier: 'value' | 'standard' | 'premium'
  description: string
  description_band: 'short' | 'medium' | 'long'
  copy_framing: 'feature_led' | 'benefit_led'
  bullets: string[]
  spec: Record<string, string>
  price_cents: number
  anchor_price_cents: number | null
  rating: number
  review_count: number
  stock_status: 'in_stock' | 'low_stock' | 'out_of_stock'
  stock_label: string | null
  shipping_line: string
  images: ImageSet | null
  is_core: boolean
  near_substitute_set_id: string | null
  varied_attribute: string | null
  badges: string[]
  alt_text: string
  reviews: ReviewSnippet[]
  season: 'spring' | 'summer' | 'fall' | 'winter' | 'holiday' | 'none'
}

export interface FacetCount {
  label: string
  count: number
}

export interface RatingFacet {
  min_rating: number
  count: number
}

export interface Facets {
  price_bands: FacetCount[]
  ratings: RatingFacet[]
}

export interface ListResponse {
  items: CatalogItem[]
  total: number
  facets: Facets
  page: number
  page_size: number
}

export interface Rail {
  rail_id: string
  policy_id: string
  title?: string
  items: CatalogItem[]
}

export interface AutocompleteSuggestion {
  item_id: string
  title: string
  category: string
}
