import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

const SeasonContext = createContext<string | null>(null)

/**
 * The active merchandising season (close-out item 4), fetched once and
 * shared so every ItemCard on a grid doesn't each make its own request.
 * Purely a display concern -- badges only. Never read by the SDK, the
 * feature pipeline, or anything that touches scoring.
 */
export function SeasonProvider({ children }: { children: ReactNode }) {
  const [season, setSeason] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/season')
      .then((r) => (r.ok ? r.json() : { season: 'none' }))
      .then((d) => setSeason(d.season))
      .catch(() => setSeason('none'))
  }, [])

  return <SeasonContext.Provider value={season}>{children}</SeasonContext.Provider>
}

export function useActiveSeason(): string | null {
  return useContext(SeasonContext)
}
