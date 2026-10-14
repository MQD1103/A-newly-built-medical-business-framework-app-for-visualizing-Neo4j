import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, ScheduleSlot } from '../types'
import { mediaUrl, weekdayLabel } from '../utils'

function formatPrice(n: number | undefined) {
  const v = Number.isFinite(n) ? Number(n) : 2.99
  return `¥${v.toFixed(2)}`
}

function Cover({ src, alt }: { src?: string; alt: string }) {
  if (src) {
    return <img src={mediaUrl(src)} alt={alt} className="course-cover-img" loading="lazy" />
  }
  return <div className="course-cover-fallback" aria-hidden="true" />
}

export default function Courses() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const focusId = Number(searchParams.get('id') || 0) || null

  const [courses, setCourses] = useState<Course[]>([])
  const [slots, setSlots] = useState<ScheduleSlot[]>([])
  const [error, setError] = useState('')
  const [activeId, setActiveId] = useState<number | null>(focusId)
  const [buying, setBuying] = useState(false)
  const [payTip, setPayTip] = useState('')

  const isAdmin = user?.role === 'admin'

  async function load() {
    const [c, s] = await Promise.all([
      api<Course[]>('/api/courses'),
      api<ScheduleSlot[]>('/api/schedule/slots'),
    ])
    setCourses(c)
    setSlots(s)
    return c
  }

  useEffect(() => {
    async function init() {
      try {
        const c = await load()
        if (focusId && c.some((x) => x.id === focusId)) {
          setActiveId(focusId)
        } else if (c.length && activeId == null) {
          setActiveId(c[0].id)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败')
      }
    }
    void init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (focusId) setActiveId(focusId)
  }, [focusId])

  const active = useMemo(
    () => courses.find((c) => c.id === activeId) ?? null,
    [courses, activeId],
  )

  const courseSlots = useMemo(
    () =>
      slots
        .filter((s) => s.course_id === activeId)
        .slice()
        .sort(
          (a, b) =>
            a.weekday - b.weekday || a.start_time.localeCompare(b.start_time),
        ),
    [slots, activeId],
  )

  function selectCourse(id: number) {
    setActiveId(id)
    setPayTip('')
    setSearchParams(id ? { id: String(id) } : {})
  }

  async function onPurchase() {
    if (!active || active.enrolled || isAdmin) return
    const ok = confirm(
      `确认支付 ${formatPrice(active.price)} 购买「${active.name}」？\n（当前为模拟支付，确认即开通）`,
    )
    if (!ok) return
    setBuying(true)
    setPayTip('')
    try {
      await api(`/api/courses/${active.id}/purchase`, { method: 'POST' })
      const list = await load()
      const updated = list.find((x) => x.id === active.id)
      setPayTip(
        updated?.enrolled
          ? '支付成功，课程已开通'
          : '支付已记录，请刷新查看',
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : '购买失败')
    } finally {
      setBuying(false)
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
      <Link to="/mall" className="back-link">
        ← 返回商城
      </Link>
      <div className="page-title">
        <div>
          <h1>课程</h1>
          <p className="sub">COPD 系列售课 · 标价见详情</p>
        </div>
      </div>

      {courses.length === 0 ? (
        <p className="muted">暂无在售课程</p>
      ) : (
        <>
          <div className="course-card-grid">
            {courses.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`course-card${activeId === c.id ? ' active' : ''}`}
                onClick={() => selectCourse(c.id)}
              >
                <div className="course-card-cover">
                  <Cover src={c.cover_url} alt={c.name} />
                  <span className="course-card-price">{formatPrice(c.price)}</span>
                </div>
                <div className="course-card-body">
                  <strong>{c.name}</strong>
                  <p className="meta">
                    {c.semester}
                    {c.enrolled ? ' · 已开通' : ''}
                  </p>
                </div>
              </button>
            ))}
          </div>

          {active && (
            <section className="item-card course-detail">
              <div className="course-detail-cover">
                <Cover src={active.cover_url} alt={active.name} />
              </div>
              <h2>{active.name}</h2>
              <p className="course-price-lg">{formatPrice(active.price)}</p>
              <p className="meta">
                {active.semester}
                {active.teacher_name ? ` · ${active.teacher_name}` : ''}
                {active.enrolled ? ' · 已开通' : ' · 未开通'}
              </p>
              {active.description ? (
                <p style={{ margin: '10px 0 0' }}>{active.description}</p>
              ) : (
                <p className="muted" style={{ margin: '10px 0 0' }}>
                  暂无简介
                </p>
              )}

              {active.enrolled || isAdmin ? (
                <div className="course-quick-links">
                  <Link to={`/materials?course_id=${active.id}`}>资料</Link>
                  <Link to={`/scores?course_id=${active.id}`}>成绩</Link>
                  <Link to={`/schedule?course_id=${active.id}`}>课表</Link>
                </div>
              ) : (
                <div className="course-buy-box">
                  <button
                    type="button"
                    className="btn primary block"
                    disabled={buying}
                    onClick={() => void onPurchase()}
                  >
                    {buying ? '支付中…' : `支付 ${formatPrice(active.price)} 开通`}
                  </button>
                  <p className="meta">模拟支付：确认后立即开通，后续可接真实支付通道</p>
                </div>
              )}
              {payTip ? <p className="ok-tip">{payTip}</p> : null}
            </section>
          )}

          {(active?.enrolled || isAdmin) && (
            <section>
              <h3 className="section-label">关联课表</h3>
              <ul className="slot-list">
                {courseSlots.map((s) => (
                  <li key={s.id} className="slot-item">
                    <time>
                      {weekdayLabel(s.weekday)}
                      <br />
                      {s.start_time}
                    </time>
                    <div>
                      <strong>
                        {s.start_time}–{s.end_time}
                      </strong>
                      <p className="meta" style={{ margin: '4px 0 0' }}>
                        {s.location || '地点待定'}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
              {courseSlots.length === 0 && (
                <p className="muted">该课程暂无课表安排</p>
              )}
            </section>
          )}
        </>
      )}
    </div>
  )
}
