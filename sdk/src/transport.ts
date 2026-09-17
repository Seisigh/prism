import type { Envelope } from './types'

const FLUSH_INTERVAL_MS = 250
const MAX_QUEUE_SIZE = 500 // §7.4: drop under backpressure, never queue unboundedly

export interface TransportConfig {
  wsUrl: string
  httpUrl: string
  sessionId: string
  code: string
}

/**
 * §7.4: telemetry never breaks the UI. Every method here is a best-effort
 * fire-and-forget — a dropped batch or a failed connection is silently
 * absorbed, never thrown back at the caller.
 */
export class Transport {
  private ws: WebSocket | null = null
  private queue: Envelope[] = []
  private flushTimer: ReturnType<typeof setInterval> | null = null
  private reconnectDelayMs = 1000
  private destroyed = false
  private onDisconnect: (() => void) | null = null
  private onReconnect: (() => void) | null = null
  private config: TransportConfig

  constructor(config: TransportConfig) {
    this.config = config
  }

  connect(callbacks?: { onDisconnect?: () => void; onReconnect?: () => void }): void {
    this.onDisconnect = callbacks?.onDisconnect ?? null
    this.onReconnect = callbacks?.onReconnect ?? null
    this.openSocket()
    this.flushTimer = setInterval(() => this.flush(), FLUSH_INTERVAL_MS)
    window.addEventListener('pagehide', this.flushViaBeacon)
  }

  private openSocket(): void {
    if (this.destroyed) return
    try {
      const url = new URL(this.config.wsUrl)
      url.searchParams.set('session_id', this.config.sessionId)
      url.searchParams.set('code', this.config.code)
      const ws = new WebSocket(url.toString())
      ws.addEventListener('open', () => {
        this.reconnectDelayMs = 1000
        this.onReconnect?.()
      })
      ws.addEventListener('close', () => {
        this.onDisconnect?.()
        this.scheduleReconnect()
      })
      ws.addEventListener('error', () => {
        // 'close' fires right after; reconnect is scheduled there.
      })
      this.ws = ws
    } catch {
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect(): void {
    if (this.destroyed) return
    this.ws = null
    setTimeout(() => this.openSocket(), this.reconnectDelayMs)
    this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, 30_000)
  }

  enqueue(envelope: Envelope): void {
    if (this.queue.length >= MAX_QUEUE_SIZE) {
      this.queue.shift() // drop the oldest — never grow unboundedly
    }
    this.queue.push(envelope)
  }

  private flush(): void {
    if (this.queue.length === 0) return
    if (this.ws?.readyState !== WebSocket.OPEN) return // stays queued (bounded) until reconnect
    try {
      this.ws.send(JSON.stringify(this.queue))
      this.queue = []
    } catch {
      // leave queued for the next flush tick
    }
  }

  private flushViaBeacon = (): void => {
    if (this.queue.length === 0) return
    try {
      const url = new URL(this.config.httpUrl)
      url.searchParams.set('session_id', this.config.sessionId)
      url.searchParams.set('code', this.config.code)
      const blob = new Blob([JSON.stringify(this.queue)], { type: 'application/json' })
      navigator.sendBeacon?.(url.toString(), blob)
      this.queue = []
    } catch {
      // best effort only — nothing to recover to on unload
    }
  }

  destroy(): void {
    this.destroyed = true
    if (this.flushTimer) clearInterval(this.flushTimer)
    window.removeEventListener('pagehide', this.flushViaBeacon)
    this.flushViaBeacon()
    this.ws?.close()
    this.ws = null
  }
}
