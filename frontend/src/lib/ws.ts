import { getAccessToken } from '@/lib/auth-store'

export type WsEvent = { type: string; data: Record<string, unknown>; at: string }

type Listener = (event: WsEvent) => void

class WsClient {
  private socket: WebSocket | null = null
  private listeners = new Set<Listener>()
  private retry = 0
  private reconnectTimer: number | null = null
  private closed = false

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) return
    if (typeof window === 'undefined') return
    const token = getAccessToken()
    if (!token) return
    this.closed = false

    const base = import.meta.env.VITE_WS_URL ?? import.meta.env.VITE_API_URL ?? window.location.origin
    const url = `${base.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(token)}`
    this.socket = new WebSocket(url)

    this.socket.onopen = () => {
      this.retry = 0
    }
    this.socket.onmessage = (msg) => {
      try {
        const event = JSON.parse(String(msg.data)) as WsEvent
        for (const l of [...this.listeners]) l(event)
      } catch {
        /* ignore malformed frames */
      }
    }
    this.socket.onclose = () => {
      this.socket = null
      if (this.closed) return
      const delay = Math.min(1000 * 2 ** this.retry, 15000)
      this.retry += 1
      this.reconnectTimer = window.setTimeout(() => this.connect(), delay)
    }
    this.socket.onerror = () => this.socket?.close()
  }

  on(listener: Listener) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  disconnect() {
    this.closed = true
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer)
    this.socket?.close()
    this.socket = null
  }
}

// Singleton across the app. Hooks call connect() in useEffect and set up the
// event listener; the connection is shared (single socket) via reference counting.
class WsRegistry extends WsClient {
  private refs = 0
  private subscribed = false

  attach() {
    this.refs += 1
    if (this.refs === 1) {
      this.subscribed = true
      this.connect()
    }
  }

  detach() {
    this.refs = Math.max(0, this.refs - 1)
    if (this.refs === 0 && this.subscribed) {
      this.subscribed = false
      this.disconnect()
    }
  }
}

export const ws = new WsRegistry()