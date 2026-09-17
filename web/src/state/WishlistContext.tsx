import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

interface WishlistContextValue {
  ids: Set<string>
  toggle: (itemId: string) => void
  has: (itemId: string) => boolean
}

const WishlistContext = createContext<WishlistContextValue | null>(null)
const STORAGE_KEY = 'prism.wishlist.v1'

function load(): Set<string> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set()
  } catch {
    return new Set()
  }
}

export function WishlistProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<Set<string>>(() => load())

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(ids)))
    } catch {
      /* non-fatal */
    }
  }, [ids])

  const toggle = useCallback((itemId: string) => {
    setIds((prev) => {
      const next = new Set(prev)
      if (next.has(itemId)) next.delete(itemId)
      else next.add(itemId)
      return next
    })
  }, [])

  const has = useCallback((itemId: string) => ids.has(itemId), [ids])

  const value = useMemo(() => ({ ids, toggle, has }), [ids, toggle, has])
  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>
}

export function useWishlist(): WishlistContextValue {
  const ctx = useContext(WishlistContext)
  if (!ctx) throw new Error('useWishlist must be used within WishlistProvider')
  return ctx
}
