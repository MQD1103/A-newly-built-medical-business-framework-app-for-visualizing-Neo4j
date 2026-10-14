import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Notice } from '../types'
import { audienceLabel, formatDateTime } from '../utils'

export default function Notices() {
  const { user } = useAuth()
  const [items, setItems] = useState<Notice[]>([])
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [audience, setAudience] = useState('all')
  const [isUrgent, setIsUrgent] = useState(false)
  const isAdmin = user?.role === 'admin'

  async function load() {
    try {
      setItems(await api<Notice[]>('/api/notices'))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    await api('/api/notices', {
      method: 'POST',
      body: JSON.stringify({ title, body, audience, is_urgent: isUrgent }),
    })
    setTitle('')
    setBody('')
    setAudience('all')
    setIsUrgent(false)
    setShowForm(false)
    await load()
  }

  async function onDelete(id: number) {
    if (!confirm('确定删除该公告？')) return
    await api(`/api/notices/${id}`, { method: 'DELETE' })
    await load()
  }

  if (error) return <p className="error screen">{error}</p>

  return (
    <div className="screen stack-gap">
      <Link to="/me" className="back-link">
        ← 返回我的
      </Link>
      <div className="page-title">
        <h1>通知公告</h1>
        {isAdmin && (
          <button
            type="button"
            className="btn small primary"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? '取消' : '发布'}
          </button>
        )}
      </div>

      {showForm && (
        <form className="form-card" onSubmit={onCreate}>
          <h2>发布公告</h2>
          <label>
            标题
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label>
            可见范围
            <select value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="all">全体</option>
              <option value="student">用户</option>
            </select>
          </label>
          <label className="rem-notify-toggle" style={{ marginBottom: 10 }}>
            <input
              type="checkbox"
              checked={isUrgent}
              onChange={(e) => setIsUrgent(e.target.checked)}
            />
            <span>标记为紧急（首页「紧急」球可见）</span>
          </label>
          <label>
            正文
            <textarea
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
            />
          </label>
          <button className="btn primary block" type="submit">
            发布
          </button>
        </form>
      )}

      <ul className="list-card">
        {items.map((n) => (
          <li key={n.id}>
            <Link to={`/notices/${n.id}`}>
              <h3>
                {n.title}
                {n.is_urgent ? <span className="badge danger">紧急</span> : null}
              </h3>
            </Link>
            <p className="meta">
              {formatDateTime(n.created_at)} · {audienceLabel(n.audience)}
            </p>
            <p className="clamp-2">{n.body}</p>
            {isAdmin && (
              <div className="row-actions">
                <button type="button" className="linkish" onClick={() => void onDelete(n.id)}>
                  删除
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="muted">暂无公告</p>}
    </div>
  )
}
