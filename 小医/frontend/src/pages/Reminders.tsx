import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, Reminder } from '../types'
import { formatDateTime } from '../utils'

function toLocalInput(iso: string): string {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function Reminders() {
  const { user } = useAuth()
  const [items, setItems] = useState<Reminder[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [dueAt, setDueAt] = useState('')
  const [url, setUrl] = useState('')
  const [courseId, setCourseId] = useState('')

  const canPickCourse = user?.role === 'admin'

  async function load() {
    try {
      const reminders = await api<Reminder[]>('/api/reminders')
      setItems(reminders)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  async function loadCourses() {
    if (!canPickCourse) return
    try {
      const path = user?.role === 'admin' ? '/api/courses/all' : '/api/courses'
      setCourses(await api<Course[]>(path))
    } catch {
      setCourses([])
    }
  }

  useEffect(() => {
    void load()
    void loadCourses()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role])

  function resetForm() {
    setTitle('')
    setContent('')
    setDueAt('')
    setUrl('')
    setCourseId('')
    setEditId(null)
  }

  function openCreate() {
    resetForm()
    setShowForm(true)
  }

  function openEdit(r: Reminder) {
    setEditId(r.id)
    setTitle(r.title)
    setContent(r.content || '')
    setDueAt(toLocalInput(r.due_at))
    setUrl(r.external_url || '')
    setCourseId(r.course_id ? String(r.course_id) : '')
    setShowForm(true)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      if (editId != null) {
        await api(`/api/reminders/${editId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            title: title.trim(),
            content: content.trim(),
            due_at: new Date(dueAt).toISOString(),
            external_url: url.trim(),
          }),
        })
      } else {
        const body: Record<string, unknown> = {
          title: title.trim(),
          content: content.trim(),
          due_at: new Date(dueAt).toISOString(),
          external_url: url.trim(),
        }
        if (canPickCourse && courseId) {
          body.course_id = Number(courseId)
        }
        await api('/api/reminders', {
          method: 'POST',
          body: JSON.stringify(body),
        })
      }
      resetForm()
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : editId ? '保存失败' : '创建失败')
    }
  }

  async function onDelete(id: number) {
    if (!confirm('确定删除？')) return
    try {
      await api(`/api/reminders/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  async function onToggleNotify(r: Reminder, enabled: boolean) {
    try {
      const updated = await api<Reminder>(`/api/reminders/${r.id}/notify`, {
        method: 'PUT',
        body: JSON.stringify({ enabled }),
      })
      setItems((prev) => prev.map((x) => (x.id === r.id ? updated : x)))
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败')
    }
  }

  function sourceLabel(source?: string) {
    if (source === 'system') return '系统'
    if (source === 'manager') return '管理'
    return '我的'
  }

  if (error) {
    return (
      <div className="screen stack-gap">
        <p className="error">{error}</p>
        <button type="button" className="btn small" onClick={() => setError('')}>
          关闭
        </button>
      </div>
    )
  }

  return (
    <div className="screen stack-gap">
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <div>
          <h1>提醒</h1>
        </div>
        <button
          type="button"
          className="btn-add"
          onClick={() => {
            if (showForm) {
              setShowForm(false)
              resetForm()
            } else {
              openCreate()
            }
          }}
          aria-label={showForm ? '取消' : '添加'}
          title={showForm ? '取消' : '添加'}
        >
          {showForm ? '×' : '+'}
        </button>
      </div>

      {showForm && (
        <form className="form-card" onSubmit={onSubmit}>
          <h2>{editId != null ? '编辑' : '添加'}</h2>
          <label>
            标题
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="任何想提醒的事"
              required
            />
          </label>
          <label>
            截止时间
            <input
              type="datetime-local"
              value={dueAt}
              onChange={(e) => setDueAt(e.target.value)}
              required
            />
          </label>
          {canPickCourse && editId == null && (
            <label>
              关联课程（可选）
              <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                <option value="">不关联 · 个人事项</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.semester ? ` · ${c.semester}` : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
          {canPickCourse && editId == null && courseId ? (
            <p className="meta">关联课程后将作为「管理」提醒发布，用户可见且不可删除</p>
          ) : null}
          {editId != null && courseId ? (
            <p className="meta">
              关联课程：{courses.find((c) => String(c.id) === courseId)?.name || '已关联'}
            </p>
          ) : null}
          <label>
            说明（可选）
            <textarea
              rows={3}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="补充说明，可留空"
            />
          </label>
          <label>
            链接（可选）
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
            />
          </label>
          <button className="btn primary block" type="submit">
            {editId != null ? '保存' : '创建'}
          </button>
        </form>
      )}

      <ul className="list-card">
        {items.map((r) => {
          const locked = r.source === 'manager' || r.source === 'system'
          return (
            <li key={r.id}>
              <h3>
                {r.title}
                <span className={`badge ${r.status === 'overdue' ? 'danger' : 'ok'}`}>
                  {r.status === 'overdue' ? '已过期' : '待完成'}
                </span>
                <span className="badge soft">{sourceLabel(r.source)}</span>
              </h3>
              <p className="meta">
                {r.course_name ? `${r.course_name} · ` : ''}
                截止 {formatDateTime(r.due_at)}
              </p>
              {r.content ? <p style={{ margin: '8px 0 0' }}>{r.content}</p> : null}
              {r.external_url && (
                <a className="ext-link" href={r.external_url} target="_blank" rel="noreferrer">
                  打开链接 →
                </a>
              )}
              <div className="row-actions rem-actions">
                {locked && (
                  <label className="rem-notify-toggle">
                    <input
                      type="checkbox"
                      checked={r.notify_enabled !== false}
                      onChange={(e) => void onToggleNotify(r, e.target.checked)}
                    />
                    <span>是否提醒</span>
                  </label>
                )}
                {r.can_edit && (
                  <button type="button" className="linkish" onClick={() => openEdit(r)}>
                    编辑
                  </button>
                )}
                {r.can_delete && (
                  <button type="button" className="linkish" onClick={() => void onDelete(r.id)}>
                    删除
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      {items.length === 0 && <p className="muted">暂无内容</p>}
    </div>
  )
}
