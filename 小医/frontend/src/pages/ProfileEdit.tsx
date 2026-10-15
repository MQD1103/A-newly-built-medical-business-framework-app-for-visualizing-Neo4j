import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { User } from '../types'

export default function ProfileEdit() {
  const { user, refresh } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [saving, setSaving] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setOk('')
    if (!fullName.trim()) {
      setError('请填写姓名')
      return
    }
    if (newPassword && newPassword !== confirm) {
      setError('两次输入的新密码不一致')
      return
    }
    setSaving(true)
    try {
      const body: Record<string, string> = { full_name: fullName.trim() }
      if (newPassword) {
        body.old_password = oldPassword
        body.new_password = newPassword
      }
      await api<User>('/api/auth/me', {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      await refresh()
      setOldPassword('')
      setNewPassword('')
      setConfirm('')
      setOk('已保存')
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="screen stack-gap">
      <Link to="/me" className="back-link">
        ← 返回我的
      </Link>
      <div className="page-title">
        <h1>修改资料</h1>
      </div>

      <form className="form-card" onSubmit={onSubmit}>
        <label>
          用户账号
          <input value={user?.username || ''} disabled />
        </label>
        <label>
          姓名
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            maxLength={100}
          />
        </label>
        <p className="meta">头像请在「我的」页点击头像更换</p>

        <h2 style={{ marginTop: 8, fontSize: '1rem' }}>修改密码（可选）</h2>
        <label>
          当前密码
          <input
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <label>
          新密码
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={4}
          />
        </label>
        <label>
          确认新密码
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
          />
        </label>

        {error && <p className="error">{error}</p>}
        {ok && <p className="ok-tip">{ok}</p>}
        <button className="btn primary block" type="submit" disabled={saving}>
          {saving ? '保存中…' : '保存'}
        </button>
      </form>
    </div>
  )
}
