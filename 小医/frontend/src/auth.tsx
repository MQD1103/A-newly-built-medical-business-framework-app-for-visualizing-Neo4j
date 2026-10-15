import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  api,
  clearActorToken,
  getActorToken,
  setActorToken,
  setToken,
  getToken,
} from './api'
import type { User } from './types'

interface AuthState {
  user: User | null
  loading: boolean
  /** 是否正处于「以此用户身份进入」状态 */
  impersonating: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
  impersonate: (userId: number) => Promise<void>
  stopImpersonating: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  // 刷新页面后仍然认得自己处于切换状态
  const [impersonating, setImpersonating] = useState(() => Boolean(getActorToken()))

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await api<User>('/api/auth/me')
      setUser(me)
    } catch {
      // 切换身份期间令牌过期：退回管理员自己的身份，而不是把管理员一起登出
      const actor = getActorToken()
      if (actor) {
        clearActorToken()
        setImpersonating(false)
        setToken(actor)
        try {
          setUser(await api<User>('/api/auth/me'))
        } catch {
          setToken(null)
          setUser(null)
        }
      } else {
        setToken(null)
        setUser(null)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    const data = await api<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setToken(data.access_token)
    const me = await api<User>('/api/auth/me')
    setUser(me)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    clearActorToken()
    setImpersonating(false)
    setUser(null)
  }, [])

  /** 管理员切换到某个用户的身份（整个界面变成对方视角） */
  const impersonate = useCallback(async (userId: number) => {
    const data = await api<{ access_token: string; user: User }>(
      '/api/auth/impersonate',
      { method: 'POST', body: JSON.stringify({ user_id: userId }) },
    )
    // 请求成功后再保存管理员自己的令牌，失败时不动现有登录态
    setActorToken(getToken())
    setToken(data.access_token)
    setUser(data.user)
    setImpersonating(true)
  }, [])

  const stopImpersonating = useCallback(async () => {
    const actor = getActorToken()
    clearActorToken()
    setImpersonating(false)
    setToken(actor)
    await refresh()
  }, [refresh])

  const value = useMemo(
    () => ({
      user,
      loading,
      impersonating,
      login,
      logout,
      refresh,
      impersonate,
      stopImpersonating,
    }),
    [
      user,
      loading,
      impersonating,
      login,
      logout,
      refresh,
      impersonate,
      stopImpersonating,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
