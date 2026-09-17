/**
 * Session/consent state. Non-negotiable #5: no event is recorded until
 * the visitor accepts, random session ID only, no accounts, no PII.
 *
 * "Browse without recording" must actually work — declining sessions get
 * no session_id and the SDK is never initialized for them (see
 * SessionProvider below, not just a flag the SDK could ignore).
 */

const CODE_ALPHABET = 'abcdefghijklmnopqrstuvwxyz0123456789'

function randomSegment(length: number): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join('')
}

/** Visitor-facing code, shape "a7f3-92kd" per COPY.md. */
export function generateCode(): string {
  return `${randomSegment(4)}-${randomSegment(4)}`
}

/** Internal session_id — never shown to the visitor, just the random
 * identifier telemetry envelopes carry. */
export function generateSessionId(): string {
  return crypto.randomUUID()
}

export type ConsentStatus = 'unset' | 'accepted' | 'declined'

const STORAGE_KEY = 'prism.session.v1'

export interface StoredSession {
  consent: ConsentStatus
  code: string | null
  sessionId: string | null
  demo: boolean
}

export function loadStoredSession(): StoredSession {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { consent: 'unset', code: null, sessionId: null, demo: false }
    const parsed = JSON.parse(raw) as StoredSession
    if (parsed.consent === 'accepted' || parsed.consent === 'declined') {
      return parsed
    }
  } catch {
    // Storage can throw (private mode, blocked). Fall through to unset —
    // the consent gate is the safe default, never silently on.
  }
  return { consent: 'unset', code: null, sessionId: null, demo: false }
}

export function saveStoredSession(session: StoredSession): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    // Telemetry must never break the UI (§7.4) — a storage failure here
    // just means the choice doesn't persist across reloads this visit.
  }
}

export function clearStoredSession(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* see saveStoredSession */
  }
}
