import { useEffect, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { ApiError, api } from '../api'
import { mediaUrl } from '../utils'

export default function Login() {
  const { user, loading, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [previewAvatar, setPreviewAvatar] = useState<string | null>(null)

  useEffect(() => {
    const name = username.trim()
    if (!name) {
      setPreviewAvatar(null)
      return
    }

    const timer = window.setTimeout(() => {
      api<{ username: string; avatar_url: string | null }>(
        `/api/auth/avatar-preview?username=${encodeURIComponent(name)}`,
      )
        .then((res) => setPreviewAvatar(res.avatar_url))
        .catch(() => setPreviewAvatar(null))
    }, 280)

    return () => window.clearTimeout(timer)
  }, [username])

  if (!loading && user) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(username.trim(), password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  function fillAccount(name: string, pass: string) {
    setUsername(name)
    setPassword(pass)
  }

  return (
    <div className="phone-stage">
      <div className="app-frame login-gradient">
        <div className="login-bg-marks" aria-hidden="true">
          <span className="bg-orb o1" />
          <span className="bg-orb o2" />
          <span className="bg-orb o3" />
          <span className="bg-orb o4" />
          <span className="bg-ring rk1" />
          <span className="bg-ring rk2" />
        </div>

        <div className="login-orb-wrap" aria-hidden="true">
          <span className="orb-ripple r1" />
          <span className="orb-ripple r2" />
          <span className="orb-ripple r3" />
          <div className={`login-orb${previewAvatar ? ' has-avatar' : ''}`}>
            {previewAvatar ? (
              <img className="orb-avatar" src={mediaUrl(previewAvatar)} alt="" />
            ) : (
              <span className="orb-shine" />
            )}
            <span className="orb-rim" />
          </div>
        </div>

        <div className="login-center">
          <h1>登录</h1>
          <p className="login-tip">欢迎使用小医</p>

          <form className="login-white-card" onSubmit={onSubmit}>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              placeholder="请输入用户账号"
              required
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="请输入密码"
              required
            />
            {error && <p className="error">{error}</p>}
            <button className="btn primary block" type="submit" disabled={submitting}>
              {submitting ? '登录中…' : '登录'}
            </button>
          </form>

          <div className="demo-box on-gradient">
            <p>演示账号（点一下填入）</p>
            <button type="button" onClick={() => fillAccount('s2024001', 'stu123')}>
              用户 s2024001 / stu123
            </button>
            <button type="button" onClick={() => fillAccount('admin', 'admin123')}>
              管理员 admin / admin123
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
