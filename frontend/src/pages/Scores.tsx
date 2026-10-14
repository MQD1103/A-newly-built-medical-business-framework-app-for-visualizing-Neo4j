import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, GradeItem } from '../types'
import { formatDateTime } from '../utils'

type StudentOpt = { id: number; full_name: string; username: string }

export default function Scores() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const canManage = user?.role === 'admin'
  const [items, setItems] = useState<GradeItem[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [students, setStudents] = useState<StudentOpt[]>([])
  const [filterCourse, setFilterCourse] = useState(searchParams.get('course_id') || '')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [courseId, setCourseId] = useState(searchParams.get('course_id') || '')
  const [studentId, setStudentId] = useState('')
  const [title, setTitle] = useState('')
  const [score, setScore] = useState('')
  const [remark, setRemark] = useState('')

  async function load() {
    try {
      const q = filterCourse ? `?course_id=${filterCourse}` : ''
      setItems(await api<GradeItem[]>(`/api/grades${q}`))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  async function loadCourses() {
    try {
      const path = user?.role === 'admin' ? '/api/courses/all' : '/api/courses'
      const list = await api<Course[]>(path)
      setCourses(list)
      if (list.length && !courseId) setCourseId(String(list[0].id))
    } catch {
      setCourses([])
    }
  }

  async function loadStudents(cid: string) {
    if (!canManage || !cid) {
      setStudents([])
      return
    }
    try {
      const list = await api<StudentOpt[]>(`/api/grades/students?course_id=${cid}`)
      setStudents(list)
      if (list.length) setStudentId(String(list[0].id))
      else setStudentId('')
    } catch {
      setStudents([])
      setStudentId('')
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

  useEffect(() => {
    if (showForm && courseId) void loadStudents(courseId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showForm, courseId])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    const n = Number(score)
    if (!courseId || !studentId || !Number.isFinite(n)) {
      setError('请完整填写课程、用户与分数')
      return
    }
    try {
      await api('/api/grades', {
        method: 'POST',
        body: JSON.stringify({
          course_id: Number(courseId),
          student_id: Number(studentId),
          title: title.trim(),
          score: n,
          remark: remark.trim(),
        }),
      })
      setTitle('')
      setScore('')
      setRemark('')
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '录入失败')
    }
  }

  async function onDelete(id: number) {
    if (!confirm('确定删除该成绩？')) return
    try {
      await api(`/api/grades/${id}`, { method: 'DELETE' })
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
          <h1>成绩</h1>
          <p className="sub">{canManage ? '录入与查看考核成绩' : '我的考核成绩'}</p>
        </div>
        {canManage && (
          <button
            type="button"
            className="btn-add"
            onClick={() => setShowForm((v) => !v)}
            aria-label={showForm ? '取消' : '录入成绩'}
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
          <h2>录入成绩</h2>
          <label>
            课程
            <select
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              required
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            用户
            <select
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              required
            >
              {students.length === 0 && <option value="">该课暂无用户</option>}
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}（{s.username}）
                </option>
              ))}
            </select>
          </label>
          <label>
            考核项
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="平时 / 期中 / 实验…"
              required
            />
          </label>
          <label>
            分数（0–100）
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={score}
              onChange={(e) => setScore(e.target.value)}
              required
            />
          </label>
          <label>
            备注（可选）
            <input value={remark} onChange={(e) => setRemark(e.target.value)} />
          </label>
          <button className="btn primary block" type="submit" disabled={!studentId}>
            保存
          </button>
        </form>
      )}

      <ul className="list-card">
        {items.map((g) => (
          <li key={g.id}>
            <h3>
              {g.title}
              <span className="badge ok">{g.score}</span>
            </h3>
            <p className="meta">
              {g.course_name}
              {canManage ? ` · ${g.student_name}` : ''}
              {' · '}
              {formatDateTime(g.created_at)}
            </p>
            {g.remark ? <p style={{ margin: '8px 0 0' }}>{g.remark}</p> : null}
            {g.can_delete && (
              <div className="row-actions">
                <button type="button" className="linkish" onClick={() => void onDelete(g.id)}>
                  删除
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="muted">暂无成绩</p>}
    </div>
  )
}
