import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  type ConsentStatus,
  type StoredSession,
  generateCode,
  generateSessionId,
  loadStoredSession,
  saveStoredSession,
} from './session'

interface SessionContextValue {
  consent: ConsentStatus
  code: string | null
  sessionId: string | null
  demo: boolean
  /** The code/id the gate will use *if* the visitor accepts. Generating
   * this is not an event — it's an unused random string until accept()
   * commits it — so it can be shown on the consent screen itself before
   * any decision, matching COPY.md's footer line from first paint. */
  pendingCode: string
  accept: () => void
  decline: () => void
  setDemo: (value: boolean) => void
  resetForNewCode: () => void
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StoredSession>(() => loadStoredSession())
  const pending = useRef({ code: generateCode(), sessionId: generateSessionId() })

  // Functional-update form so every derived callback below has a stable
  // identity (no `state` in its deps). The earlier version rebuilt
  // `setDemo` on every state change and ProfilePanel's effect depended on
  // it, which looped: open panel -> setDemo(true) -> state changes ->
  // new setDemo identity -> effect re-fires -> setDemo(true) -> ... until
  // React's "Maximum update depth exceeded".
  const persist = useCallback((updater: StoredSession | ((prev: StoredSession) => StoredSession)) => {
    setState((prev) => {
      const next = typeof updater === 'function' ? (updater as (p: StoredSession) => StoredSession)(prev) : updater
      saveStoredSession(next)
      return next
    })
  }, [])

  const accept = useCallback(() => {
    persist({ consent: 'accepted', code: pending.current.code, sessionId: pending.current.sessionId, demo: false })
  }, [persist])

  const decline = useCallback(() => {
    persist({ consent: 'declined', code: null, sessionId: null, demo: false })
  }, [persist])

  const setDemo = useCallback(
    (value: boolean) => {
      persist((prev) => (prev.demo === value ? prev : { ...prev, demo: value }))
    },
    [persist],
  )

  const resetForNewCode = useCallback(() => {
    persist({ consent: 'accepted', code: generateCode(), sessionId: generateSessionId(), demo: false })
  }, [persist])

  const value = useMemo(
    () => ({ ...state, pendingCode: pending.current.code, accept, decline, setDemo, resetForNewCode }),
    [state, accept, decline, setDemo, resetForNewCode],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
