import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, CourseLessons, Lesson, ScheduleSlot } from '../types'
import { formatPrice, mediaUrl, priceText, weekdayLabel } from '../utils'

/** 课程价格兜底值，与后端 courses.py 的默认售价保持一致 */
const PRICE_FALLBACK = 2.99

function Cover({ src, alt }: { src?: string; alt: string }) {
  if (src) {
    return <img src={mediaUrl(src)} alt={alt} className="course-cover-img" loading="lazy" />
  }
  return <div className="course-cover-fallback" aria-hidden="true" />
}

function durationLabel(seconds: number): string {
  const total = Math.max(0, Math.round(seconds || 0))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
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
  const [lessonData, setLessonData] = useState<CourseLessons | null>(null)
  const [activeLessonId, setActiveLessonId] = useState<number | null>(null)
  const [lessonError, setLessonError] = useState('')
  const [marking, setMarking] = useState(false)

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

  useEffect(() => {
    if (activeId == null) {
      setLessonData(null)
      setActiveLessonId(null)
      return
    }
    let cancelled = false
    setLessonData(null)
    setLessonError('')
    api<CourseLessons>(`/api/courses/${activeId}/lessons`)
      .then((data) => {
        if (cancelled) return
        setLessonData(data)
        setActiveLessonId((current) => {
          const same = data.lessons.find((x) => x.id === current)
          if (same && !same.locked) return current
          return (
            data.lessons.find((x) => !x.locked)?.id ??
            data.lessons[0]?.id ??
            null
          )
        })
      })
      .catch((e) => {
        if (!cancelled) {
          setLessonError(e instanceof Error ? e.message : '课时加载失败')
        }
      })
    return () => {
      cancelled = true
    }
  }, [activeId])

  const activeLesson = useMemo(
    () => lessonData?.lessons.find((x) => x.id === activeLessonId) ?? null,
    [lessonData, activeLessonId],
  )

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
      `确认支付 ${formatPrice(active.price, PRICE_FALLBACK)} 购买「${active.name}」？\n（当前为模拟支付，确认即开通）`,
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

  async function markLessonDone(lesson: Lesson) {
    if (marking || lesson.locked || !lessonData) return
    setMarking(true)
    setLessonError('')
    try {
      await api(`/api/courses/lessons/${lesson.id}/progress`, {
        method: 'POST',
        body: JSON.stringify({
          position_seconds: lesson.duration_seconds || 0,
          completed: true,
        }),
      })
      const refreshed = await api<CourseLessons>(
        `/api/courses/${lessonData.course_id}/lessons`,
      )
      setLessonData(refreshed)
    } catch (e) {
      setLessonError(e instanceof Error ? e.message : '记录学习进度失败')
    } finally {
      setMarking(false)
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
          <p className="sub">
            {isAdmin ? 'COPD 系列课程 · 管理员免费开放' : 'COPD 系列售课 · 标价见详情'}
          </p>
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
                  <span className="course-card-price">
                    {priceText(c.price, isAdmin, PRICE_FALLBACK)}
                  </span>
                </div>
                <div className="course-card-body">
                  <strong>{c.name}</strong>
                  <p className="meta">
                    {c.semester}
                    {isAdmin ? ' · 免费开放' : c.enrolled ? ' · 已开通' : ''}
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
              <p className={`course-price-lg${isAdmin ? ' is-free' : ''}`}>
                {priceText(active.price, isAdmin, PRICE_FALLBACK)}
              </p>
              <p className="meta">
                {active.semester}
                {active.teacher_name ? ` · ${active.teacher_name}` : ''}
                {isAdmin ? ' · 免费开放' : active.enrolled ? ' · 已开通' : ' · 未开通'}
              </p>
              {active.description ? (
                <p style={{ margin: '10px 0 0' }}>{active.description}</p>
              ) : (
                <p className="muted" style={{ margin: '10px 0 0' }}>
                  暂无简介
                </p>
              )}

              {active.enrolled || isAdmin ? (
                <>
                  <div className="course-quick-links">
                    <Link to={`/materials?course_id=${active.id}`}>资料</Link>
                    <Link to={`/scores?course_id=${active.id}`}>成绩</Link>
                    <Link to={`/schedule?course_id=${active.id}`}>课表</Link>
                  </div>
                  {isAdmin ? <p className="ok-tip">管理员免费开放，无需购买</p> : null}
                </>
              ) : (
                <div className="course-buy-box">
                  <button
                    type="button"
                    className="btn primary block"
                    disabled={buying}
                    onClick={() => void onPurchase()}
                  >
                    {buying ? '支付中…' : `支付 ${formatPrice(active.price, PRICE_FALLBACK)} 开通`}
                  </button>
                  <p className="meta">模拟支付：确认后立即开通，后续可接真实支付通道</p>
                </div>
              )}
              {payTip ? <p className="ok-tip">{payTip}</p> : null}
            </section>
          )}

          {active && (
            <section className="item-card lesson-section">
              <div className="lesson-head">
                <h3 className="section-label">课时学习</h3>
                {lessonData ? (
                  <span className="lesson-count">
                    已完成 {lessonData.completed_lessons}/{lessonData.total_lessons}
                  </span>
                ) : null}
              </div>
              {lessonError ? <p className="error">{lessonError}</p> : null}
              {!lessonData ? (
                <p className="muted">课时加载中…</p>
              ) : lessonData.lessons.length === 0 ? (
                <p className="muted">该课程暂无课时</p>
              ) : (
                <>
                  <div className="lesson-player-wrap">
                    {activeLesson &&
                    !activeLesson.locked &&
                    activeLesson.video_url ? (
                      <video
                        key={activeLesson.id}
                        className="lesson-player"
                        src={mediaUrl(activeLesson.video_url)}
                        poster={mediaUrl(
                          activeLesson.video_url.replace(/\.mp4$/i, '.jpg'),
                        )}
                        controls
                        playsInline
                        preload="metadata"
                        onEnded={() => void markLessonDone(activeLesson)}
                      />
                    ) : (
                      <div className="lesson-player-empty">
                        {activeLesson?.locked
                          ? '购买后可观看该课时'
                          : activeLesson
                            ? '该课时暂未配置视频'
                            : '请选择课时'}
                      </div>
                    )}
                    {activeLesson ? (
                      <div className="lesson-now">
                        <strong>{activeLesson.title}</strong>
                        <span className="meta">
                          {durationLabel(activeLesson.duration_seconds)}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  <ul className="lesson-list">
                    {lessonData.lessons.map((lesson, index) => (
                      <li key={lesson.id}>
                        <button
                          type="button"
                          className={`lesson-row${
                            lesson.id === activeLessonId ? ' active' : ''
                          }${lesson.locked ? ' locked' : ''}`}
                          disabled={lesson.locked}
                          onClick={() => setActiveLessonId(lesson.id)}
                        >
                          <span className="lesson-index">
                            {String(index + 1).padStart(2, '0')}
                          </span>
                          <span className="lesson-row-main">
                            <strong>{lesson.title}</strong>
                            <span className="meta">
                              {durationLabel(lesson.duration_seconds)}
                              {lesson.locked
                                ? ' · 购买后解锁'
                                : lesson.is_trial
                                  ? ' · 可试看'
                                  : ''}
                            </span>
                          </span>
                          <span className="lesson-state">
                            {lesson.locked ? '锁定' : '播放'}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {activeLesson && !activeLesson.locked ? (
                    <button
                      type="button"
                      className="btn small lesson-done"
                      disabled={marking}
                      onClick={() => void markLessonDone(activeLesson)}
                    >
                      {marking ? '记录中…' : '标记本节已学完'}
                    </button>
                  ) : null}
                </>
              )}
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
