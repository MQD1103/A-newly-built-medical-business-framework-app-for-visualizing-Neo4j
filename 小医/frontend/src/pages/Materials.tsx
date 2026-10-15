import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, CourseMaterial } from '../types'
import { formatDateTime } from '../utils'

export default function Materials() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const canManage = user?.role === 'admin'
  const [items, setItems] = useState<CourseMaterial[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [filterCourse, setFilterCourse] = useState(searchParams.get('course_id') || '')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [note, setNote] = useState('')
  const [courseId, setCourseId] = useState(searchParams.get('course_id') || '')

  async function load() {
    try {
      const q = filterCourse ? `?course_id=${filterCourse}` : ''
      setItems(await api<CourseMaterial[]>(`/api/materials${q}`))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  async function loadCourses() {
    try {
      const path =
        user?.role === 'admin'
          ? '/api/courses/all'
          : '/api/courses'
      const list = await api<Course[]>(path)
      setCourses(list)
      if (list.length && !courseId) setCourseId(String(list[0].id))
    } catch {
      setCourses([])
    }
  }

  useEffect(() => {
    const fromUrl = searchParams.get('course_id') || ''
    if (fromUrl) {
      setFilterCourse(fromUrl)
      setCourseId(fromUrl)
    }
  }, [searchParams])

  useEffect(() => {
    void load()
    void loadCourses()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role, filterCourse])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    if (!courseId) {
      setError('请选择课程')
      return
    }
    try {
      await api('/api/materials', {
        method: 'POST',
        body: JSON.stringify({
          course_id: Number(courseId),
          title: title.trim(),
          url: url.trim(),
          note: note.trim(),
        }),
      })
      setTitle('')
      setUrl('')
      setNote('')
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '发布失败')
    }
  }

  async function onDelete(id: number) {
    if (!confirm('确定删除该资料？')) return
    try {
      await api(`/api/materials/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
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
      <Link to="/" className="back-link">
        ← 返回首页
      </Link>
      <div className="page-title">
        <div>
          <h1>课程资料</h1>
          <p className="sub">课件链接与说明</p>
        </div>
        {canManage && (
          <button
            type="button"
            className="btn-add"
            onClick={() => setShowForm((v) => !v)}
            aria-label={showForm ? '取消' : '添加资料'}
          >
            {showForm ? '×' : '+'}
          </button>
        )}
      </div>

      {courses.length > 0 && (
        <label className="inline-filter">
          课程筛选
          <select value={filterCourse} onChange={(e) => setFilterCourse(e.target.value)}>
            <option value="">全部</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {showForm && canManage && (
        <form className="form-card" onSubmit={onCreate}>
          <h2>发布资料</h2>
          <label>
            课程
            <select value={courseId} onChange={(e) => setCourseId(e.target.value)} required>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            标题
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="课件 / 实验指南…"
              required
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
          <label>
            说明（可选）
            <textarea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="补充说明"
            />
          </label>
          <button className="btn primary block" type="submit">
            发布
          </button>
        </form>
      )}

      <ul className="list-card">
        {items.map((m) => (
          <li key={m.id}>
            <h3>{m.title}</h3>
            <p className="meta">
              {m.course_name} · {formatDateTime(m.created_at)}
            </p>
            {m.note ? <p style={{ margin: '8px 0 0' }}>{m.note}</p> : null}
            {m.url ? (
              <a className="ext-link" href={m.url} target="_blank" rel="noreferrer">
                打开链接 →
              </a>
            ) : null}
            {m.can_delete && (
              <div className="row-actions">
                <button type="button" className="linkish" onClick={() => void onDelete(m.id)}>
                  删除
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="muted">暂无资料</p>}
    </div>
  )
}
