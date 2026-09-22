import { getAccessToken, setTokens } from '@/lib/auth-store'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

const ACCESS_KEY = 'internflow.access'
const REFRESH_KEY = 'internflow.refresh'

interface RefreshResult {
  access_token: string
  refresh_token: string
}

async function tryRefresh(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_KEY)
  if (!refresh) return false
  try {
    const res = await apiFetch<RefreshResult>('/api/v1/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refresh }),
    })
    localStorage.setItem(ACCESS_KEY, res.access_token)
    localStorage.setItem(REFRESH_KEY, res.refresh_token)
    setTokens({ accessToken: res.access_token, refreshToken: res.refresh_token })
    return true
  } catch {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    setTokens({ accessToken: null, refreshToken: null })
    return false
  }
}

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
  _retry = true,
): Promise<T> {
  const token = getAccessToken()
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  }
  if (!(init.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })

  if (res.status === 401 && _retry && !path.includes('/auth/')) {
    const refreshed = await tryRefresh()
    if (refreshed) return apiFetch<T>(path, init, false)
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (typeof body.detail === 'object' && body.detail) {
        const first = Object.values(body.detail)[0] as { msg?: string } | undefined
        if (first?.msg) detail = first.msg
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, file: File, extra?: Record<string, string>) => {
    const form = new FormData()
    form.append('file', file)
    for (const [k, v] of Object.entries(extra ?? {})) form.append(k, v)
    return apiFetch<T>(path, { method: 'POST', body: form })
  },
  /** Fetch a binary payload with the bearer token and trigger a browser download. */
  download: async (path: string) => {
    const token = getAccessToken()
    const res = await fetch(`${API_BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
      throw new ApiError(res.status, typeof body?.detail === 'string' ? body.detail : res.statusText)
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') ?? ''
    const match = /filename="?([^";]+)"?/.exec(disposition)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = match ? match[1] : 'download'
    a.click()
    URL.revokeObjectURL(a.href)
  },
}