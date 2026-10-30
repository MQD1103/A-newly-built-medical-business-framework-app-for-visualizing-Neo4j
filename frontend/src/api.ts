const TOKEN_KEY = 'edu_token'
/** 「以此用户身份进入」期间，管理员自己的令牌先存这里，退出切换时还原 */
const ACTOR_TOKEN_KEY = 'edu_actor_token'

/** 团队在 frontend/.env 填写 VITE_API_BASE；留空则走本机 Vite 代理 */
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || ''

export function apiUrl(path: string): string {
  if (path.startsWith('http')) return path
  return `${API_BASE}${path}`
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getActorToken(): string | null {
  return localStorage.getItem(ACTOR_TOKEN_KEY)
}

export function setActorToken(token: string | null) {
  if (token) localStorage.setItem(ACTOR_TOKEN_KEY, token)
  else localStorage.removeItem(ACTOR_TOKEN_KEY)
}

export function clearActorToken() {
  localStorage.removeItem(ACTOR_TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(apiUrl(path), { ...options, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
      if (Array.isArray(detail)) {
        detail = detail.map((d: { msg?: string }) => d.msg).join('; ')
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

/** 上传文件（FormData，不强制 JSON Content-Type） */
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(apiUrl(path), { method: 'POST', headers, body: form })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
      if (Array.isArray(detail)) {
        detail = detail.map((d: { msg?: string }) => d.msg).join('; ')
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, String(detail))
  }
  return res.json()
}
