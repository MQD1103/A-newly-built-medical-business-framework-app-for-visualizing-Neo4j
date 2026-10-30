import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, ScheduleSlot } from '../types'
import { weekdayLabel } from '../utils'

/** 课程分类标签：整包课 / 单课 / 入门课 */
const CAT_LABEL: Record<string, string> = {
  intro: '入门课',
  single: '单课',
  bundle: '整包课',
}

export default function Schedule() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const filterFromUrl = searchParams.get('course_id') || ''

  const [slots, setSlots] = useState<ScheduleSlot[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [error, setError] = useState('')
  const [activeDay, setActiveDay] = useState(() =>
    new Date().getDay() === 0 ? 6 : new Date().getDay() - 1,
  )
  const [showForm, setShowForm] = useState(false)
  const [filterCourseId, setFilterCourseId] = useState(filterFromUrl)
  // 课程分类筛选：全部 / 入门课 / 单课 / 整包课
  const [cat, setCat] = useState<'all' | 'intro' | 'single' | 'bundle'>('all')

  const canManageSlot = user?.role === 'admin'

  const [courseId, setCourseId] = useState('')
  const [weekday, setWeekday] = useState('0')
  const [start, setStart] = useState('08:00')
  const [end, setEnd] = useState('09:40')
  const [location, setLocation] = useState('')

  const courseMap = useMemo(() => {
    const m = new Map<number, Course>()
    for (const c of courses) m.set(c.id, c)
    return m
  }, [courses])

  async function load() {
    try {
      const [s, c] = await Promise.all([
        api<ScheduleSlot[]>('/api/schedule/slots'),
        api<Course[]>(user?.role === 'admin' ? '/api/courses/all' : '/api/courses'),
      ])
      setSlots(s)
      setCourses(c)
      if (c.length) setCourseId((prev) => prev || String(c[0].id))
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role])

  useEffect(() => {
    setFilterCourseId(filterFromUrl)
  }, [filterFromUrl])

  const visibleSlots = useMemo(() => {
    let list = slots
    if (cat !== 'all') {
      list = list.filter(
        (s) => (courseMap.get(s.course_id)?.course_type ?? 'single') === cat,
      )
    }
    if (filterCourseId) {
      list = list.filter((s) => String(s.course_id) === filterCourseId)
    }
    return list
  }, [slots, filterCourseId, cat, courseMap])

  const counts = useMemo(() => {
    const map = Array.from({ length: 7 }, () => 0)
    for (const s of visibleSlots) map[s.weekday] += 1
    return map
  }, [visibleSlots])

  const daySlots = useMemo(
    () =>
      visibleSlots
        .filter((s) => s.weekday === activeDay)
        .sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [visibleSlots, activeDay],
  )

  function onFilterChange(id: string) {
    setFilterCourseId(id)
    if (id) setSearchParams({ course_id: id })
    else setSearchParams({})
  }

  async function onAddSlot(e: FormEvent) {
    e.preventDefault()
    await api('/api/schedule/slots', {
      method: 'POST',
      body: JSON.stringify({
        course_id: Number(courseId),
        weekday: Number(weekday),
        start_time: start,
        end_time: end,
        location,
      }),
    })
    setLocation('')
    setShowForm(false)
    await load()
  }

  async function onDeleteSlot(id: number) {
    if (!confirm('删除该课表项？')) return
    await api(`/api/schedule/slots/${id}`, { method: 'DELETE' })
    await load()
  }

  if (error) return <p className="error screen">{error}</p>

  return (
    <div className="screen stack-gap">
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <h1>课表</h1>
        {canManageSlot && (
          <button
            type="button"
            className="btn small primary"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? '取消' : '加课'}
          </button>
        )}
      </div>

      <div className="sched-cats">
        {(
          [
            ['all', '全部'],
            ['intro', '入门课'],
            ['single', '单课'],
            ['bundle', '整包课'],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={`sched-cat${cat === k ? ' active' : ''}`}
            onClick={() => setCat(k)}
          >
            {label}
          </button>
        ))}
      </div>

      {courses.length > 0 && (
        <label className="inline-filter">
          按课程筛选
          <select value={filterCourseId} onChange={(e) => onFilterChange(e.target.value)}>
            <option value="">全部课程</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="day-scroll">
        {[0, 1, 2, 3, 4, 5, 6].map((d) => (
          <button
            key={d}
            type="button"
            className={`day-chip${counts[d] ? ' has' : ''}${activeDay === d ? ' has' : ''}`}
            style={
              activeDay === d
                ? {
                    background: 'linear-gradient(180deg,#5ba3f5,#3b86e0)',
                    color: '#fff',
                    borderColor: 'transparent',
                  }
                : undefined
            }
            onClick={() => setActiveDay(d)}
          >
            <strong style={activeDay === d ? { color: '#fff' } : undefined}>
              {weekdayLabel(d)}
            </strong>
            <span style={activeDay === d ? { color: 'rgba(255,255,255,.85)' } : undefined}>
              {counts[d] ? `${counts[d]}节` : '无课'}
            </span>
          </button>
        ))}
      </div>

      {showForm && (
        <form className="form-card" onSubmit={onAddSlot}>
          <h2>添加课表项</h2>
          <label>
            课程
            <select value={courseId} onChange={(e) => setCourseId(e.target.value)} required>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · {c.semester}
                </option>
              ))}
            </select>
          </label>
          <label>
            星期
            <select value={weekday} onChange={(e) => setWeekday(e.target.value)}>
              {[0, 1, 2, 3, 4, 5, 6].map((d) => (
                <option key={d} value={d}>
                  {weekdayLabel(d)}
                </option>
              ))}
            </select>
          </label>
          <label>
            开始
            <input value={start} onChange={(e) => setStart(e.target.value)} pattern="\d{2}:\d{2}" />
          </label>
          <label>
            结束
            <input value={end} onChange={(e) => setEnd(e.target.value)} pattern="\d{2}:\d{2}" />
          </label>
          <label>
            教室
            <input value={location} onChange={(e) => setLocation(e.target.value)} />
          </label>
          <button className="btn primary block" type="submit" disabled={!courses.length}>
            添加
          </button>
        </form>
      )}

      <ul className="slot-list">
        {daySlots.map((s) => {
          const course = courseMap.get(s.course_id)
          return (
            <li key={s.id} className="slot-item">
              <time>
                {s.start_time}
                <br />
                {s.end_time}
              </time>
              <div>
                <Link to={`/courses?id=${s.course_id}`} className="slot-course-link">
                  <strong>{s.course_name}</strong>
                  <span
                    className={`slot-cat cat-${course?.course_type ?? 'single'}`}
                  >
                    {CAT_LABEL[course?.course_type ?? 'single'] ?? '单课'}
                  </span>
                </Link>
                <p className="meta" style={{ margin: '4px 0 0' }}>
                  {s.location || '地点待定'}
                  {course?.teacher_name ? ` · ${course.teacher_name}` : ''}
                  {course?.semester ? ` · ${course.semester}` : ''}
                </p>
              </div>
              {canManageSlot && (
                <button type="button" className="linkish" onClick={() => void onDeleteSlot(s.id)}>
                  删
                </button>
              )}
            </li>
          )
        })}
      </ul>
      {daySlots.length === 0 && <p className="muted">这天没有课</p>}
    </div>
  )
}
