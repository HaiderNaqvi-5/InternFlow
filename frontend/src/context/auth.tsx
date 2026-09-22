import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { authApi, refreshAccessToken } from '@/lib/auth-api'
import { setTokens } from '@/lib/auth-store'
import type { UserMe } from '@/lib/types'

const ACCESS_KEY = 'internflow.access'
const REFRESH_KEY = 'internflow.refresh'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserMe | null
  loading: boolean
}

type AuthStore = AuthState & {
  login: (email: string, password: string) => Promise<UserMe>
  setFirstPassword: (email: string, currentPassword: string, newPassword: string) => Promise<void>
  logout: () => Promise<void>
  tryRefresh: () => Promise<boolean>
  setAccessToken: (token: string) => void
  updateUser: (user: UserMe) => void
}

let store: AuthStore | null = null

function readTokens(): { accessToken: string | null; refreshToken: string | null } {
  if (typeof window === 'undefined') return { accessToken: null, refreshToken: null }
  return { accessToken: localStorage.getItem(ACCESS_KEY), refreshToken: localStorage.getItem(REFRESH_KEY) }
}

async function doLogin(email: string, password: string): Promise<UserMe> {
  const res = await authApi.login(email, password)
  return doPostLogin(res)
}

async function doPostLogin(res: Awaited<ReturnType<typeof authApi.login>>): Promise<UserMe> {
  localStorage.setItem(ACCESS_KEY, res.access_token)
  localStorage.setItem(REFRESH_KEY, res.refresh_token)
  const me = await authApi.me()
  if (store) {
    store.setAccessToken(res.access_token)
    store.updateUser(me)
  }
  return me
}

export function useAuthStore(): AuthStore {
  if (!store) throw new Error('AuthStore not mounted (wrap app in <AuthProvider>)')
  return store
}

const AuthContext = createContext<AuthStore | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => ({
    ...readTokens(),
    user: null,
    loading: true,
  }))

  const setAccessToken = useCallback((token: string) => {
    setState((s) => ({ ...s, accessToken: token }))
  }, [])

  const updateUser = useCallback((user: UserMe) => {
    setState((s) => ({ ...s, user }))
  }, [])

  const tryRefresh = useCallback(async (): Promise<boolean> => {
    const refresh = readTokens().refreshToken
    if (!refresh) return false
    try {
      const res = await refreshAccessToken(refresh)
      localStorage.setItem(ACCESS_KEY, res.access_token)
      localStorage.setItem(REFRESH_KEY, res.refresh_token)
      setState((s) => ({ ...s, accessToken: res.access_token, refreshToken: res.refresh_token }))
      return true
    } catch {
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
      setState((s) => ({ ...s, accessToken: null, refreshToken: null, user: null }))
      return false
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => doLogin(email, password), [])

  const setFirstPassword = useCallback(
    async (email: string, currentPassword: string, newPassword: string) => {
      await authApi.firstPassword(email, currentPassword, newPassword)
      await doLogin(email, newPassword)
    },
    [],
  )

  const logout = useCallback(async () => {
    const refresh = readTokens().refreshToken
    if (refresh) {
      try {
        await authApi.logout()
      } catch {
        /* ignore */
      }
    }
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    setState({ accessToken: null, refreshToken: null, user: null, loading: false })
  }, [])

  const value = useMemo<AuthStore>(
    () => ({ ...state, login, setFirstPassword, logout, tryRefresh, setAccessToken, updateUser }),
    [state, login, setFirstPassword, logout, tryRefresh, setAccessToken, updateUser],
  )

  useEffect(() => {
    setTokens({ accessToken: state.accessToken, refreshToken: state.refreshToken })
  }, [state.accessToken, state.refreshToken])

  useEffect(() => {
    store = value
    const boot = async () => {
      const { accessToken } = readTokens()
      setState((s) => ({ ...s, loading: true }))
      if (!accessToken) {
        setState((s) => ({ ...s, loading: false }))
        return
      }
      const ok = await tryRefresh()
      if (ok) {
        try {
          const me = await authApi.me()
          setState((s) => ({ ...s, user: me, loading: false }))
        } catch {
          setState((s) => ({ ...s, user: null, loading: false }))
        }
      } else {
        setState((s) => ({ ...s, loading: false }))
      }
    }
    void boot()
    return () => {
      store = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export { AuthContext }