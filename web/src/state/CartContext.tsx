import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { CatalogItem } from '../lib/types'

export interface CartLine {
  item: CatalogItem
  quantity: number
}

interface CartContextValue {
  lines: CartLine[]
  count: number
  subtotalCents: number
  add: (item: CatalogItem, quantity?: number) => void
  remove: (itemId: string) => void
  setQuantity: (itemId: string, quantity: number) => void
  clear: () => void
}

const CartContext = createContext<CartContextValue | null>(null)
const STORAGE_KEY = 'prism.cart.v1'

function load(): CartLine[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as CartLine[]) : []
  } catch {
    return []
  }
}

function save(lines: CartLine[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lines))
  } catch {
    /* non-fatal */
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(() => load())

  useEffect(() => save(lines), [lines])

  const add = useCallback((item: CatalogItem, quantity = 1) => {
    setLines((prev) => {
      const existing = prev.find((l) => l.item.item_id === item.item_id)
      if (existing) {
        return prev.map((l) =>
          l.item.item_id === item.item_id ? { ...l, quantity: l.quantity + quantity } : l,
        )
      }
      return [...prev, { item, quantity }]
    })
  }, [])

  const remove = useCallback((itemId: string) => {
    setLines((prev) => prev.filter((l) => l.item.item_id !== itemId))
  }, [])

  const setQuantity = useCallback((itemId: string, quantity: number) => {
    setLines((prev) => prev.map((l) => (l.item.item_id === itemId ? { ...l, quantity } : l)))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const count = useMemo(() => lines.reduce((sum, l) => sum + l.quantity, 0), [lines])
  const subtotalCents = useMemo(
    () => lines.reduce((sum, l) => sum + l.quantity * l.item.price_cents, 0),
    [lines],
  )

  const value = useMemo(
    () => ({ lines, count, subtotalCents, add, remove, setQuantity, clear }),
    [lines, count, subtotalCents, add, remove, setQuantity, clear],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within CartProvider')
  return ctx
}
