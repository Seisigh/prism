import { PrismSDK } from '@prism/sdk'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { api, getCachedNearSubstituteSetId } from '../lib/api'
import type { Surface } from '@prism/sdk'
import { useSession } from './SessionContext'

const PrismSDKContext = createContext<PrismSDK | null>(null)

function surfaceForPath(pathname: string): Surface {
  if (pathname.startsWith('/category')) return 'category'
  if (pathname.startsWith('/search')) return 'search'
  if (pathname.startsWith('/item/')) return 'detail'
  if (pathname.startsWith('/compare')) return 'compare'
  if (pathname.startsWith('/cart') || pathname.startsWith('/checkout')) return 'cart'
  return 'home'
}

/**
 * Owns the one PrismSDK instance for the app's lifetime. Only ever
 * constructed when consent is 'accepted' — a declined session never
 * reaches this provider's init effect, and "Browse without recording"
 * (COPY.md §1) is enforced structurally, not by a flag the SDK could
 * ignore, because no SDK instance exists at all in that case.
 */
export function PrismSDKProvider({ children }: { children: ReactNode }) {
  const { consent, sessionId, code } = useSession()
  const location = useLocation()
  const surfaceRef = useRef<Surface>('home')
  const [sdk, setSdk] = useState<PrismSDK | null>(null)

  surfaceRef.current = surfaceForPath(location.pathname)

  useEffect(() => {
    if (consent !== 'accepted' || !sessionId || !code) return
    let cancelled = false
    let instance: PrismSDK | null = null

    api
      .brandTokens()
      .then(({ tokens }) => {
        if (cancelled) return
        instance = new PrismSDK({
          wsUrl: `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`,
          httpUrl: `${window.location.origin}/api/events`,
          sessionId,
          code,
          brandTokens: tokens,
          getSurface: () => surfaceRef.current,
          getNearSubstituteSetId: getCachedNearSubstituteSetId,
        })
        instance.init()
        setSdk(instance)
      })
      .catch(() => {
        // §7.4: telemetry never breaks the UI — a failed brand-token
        // fetch just means directed_search classification degrades to
        // token-count-only until the next reload, not that the whole
        // SDK fails to start.
        if (cancelled) return
        instance = new PrismSDK({
          wsUrl: `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`,
          httpUrl: `${window.location.origin}/api/events`,
          sessionId,
          code,
          getSurface: () => surfaceRef.current,
          getNearSubstituteSetId: getCachedNearSubstituteSetId,
        })
        instance.init()
        setSdk(instance)
      })

    return () => {
      cancelled = true
      instance?.destroy()
      setSdk(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consent, sessionId, code])

  return <PrismSDKContext.Provider value={sdk}>{children}</PrismSDKContext.Provider>
}

/** Returns null when recording is off or the SDK hasn't finished
 * connecting yet — every call site must handle that (optional chaining),
 * which is the point: instrumentation is never load-bearing for the UI. */
export function usePrismSDK(): PrismSDK | null {
  return useContext(PrismSDKContext)
}
