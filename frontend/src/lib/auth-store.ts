// Forkable token store consumed by the API client and WebSocket client,
// kept in sync by AuthProvider. Kept outside React so plain modules can read
// the current access token without subscribing to re-renders.

export interface TokenState {
  accessToken: string | null
  refreshToken: string | null
}

let state: TokenState = { accessToken: null, refreshToken: null }

const listeners = new Set<(tokens: TokenState) => void>()

export function setTokens(tokens: TokenState) {
  state = tokens
  for (const l of listeners) l(state)
}

export function getTokens(): TokenState {
  return state
}

export function getAccessToken(): string | null {
  return state.accessToken
}

export function subscribeAuth(listener: (tokens: TokenState) => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}