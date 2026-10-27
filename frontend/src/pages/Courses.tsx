import { useEffect, useMemo, useRef, useState } from 'react'
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

/** 板块测验的题目（后端不下发答案） */
interface QuizQuestion {
  id: number
  question: string
  options: string[]
}

/** 提交后后端返回的判分结果 */
interface QuizResult {
  course_id: number
  score: number
  total: number
  details: {
    question_id: number
    question: string
    chosen: number
    answer_index: number
    correct: boolean
    explanation: string
    lesson_id: number | null
    lesson_title: string
  }[]
}

const OPTION_LABELS = ['A', 'B', 'C', 'D', 'E', 'F']

/** 课后小自测题（后端 /api/lesson-quiz 下发，前端即时判分） */
interface LessonCheckItem {
  question: string
  options: string[]
  answer: number
  explanation: string
}

/** 检索用归一化：统一小写并去掉空白与常见标点 */
function normalize(text: string): string {
  return text.toLowerCase().replace(/[\s,，。、；;：:/／|·\-—_]+/g, '')
}

/** 课时索引：标题 + 要点，用于「知识点关键词」检索 */
interface LessonIndexItem {
  title: string
  text: string
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

  // 课程搜索：关键词 + 课时知识点索引（首屏后台预取，检索全在本地完成）
  const [keyword, setKeyword] = useState(() => searchParams.get('kw') || '')
  const [lessonIndex, setLessonIndex] = useState<Record<number, LessonIndexItem[]>>({})


  // 板块测验状态
  const [quizOpen, setQuizOpen] = useState(false)
  const [quizLoading, setQuizLoading] = useState(false)
  const [quizError, setQuizError] = useState('')
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([])
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({})
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null)
  const [quizSubmitting, setQuizSubmitting] = useState(false)

  // 课后小自测（按课时标题匹配，即时判分，不进成绩）
  const [checks, setChecks] = useState<Record<string, LessonCheckItem>>({})
  const [checkPick, setCheckPick] = useState<number | null>(null)
  const playerRef = useRef<HTMLDivElement>(null)

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

  // 后台把每门课的课时标题+要点抓成检索索引，失败不影响其他功能
  useEffect(() => {
    if (!courses.length) return
    let cancelled = false
    void Promise.allSettled(
      courses.map(async (c) => {
        const data = await api<CourseLessons>(`/api/courses/${c.id}/lessons`)
        const items: LessonIndexItem[] = data.lessons.map((l) => ({
          title: l.title,
          text: normalize(`${l.title} ${l.summary ?? ''}`),
        }))
        return [c.id, items] as const
      }),
    ).then((results) => {
      if (cancelled) return
      const map: Record<number, LessonIndexItem[]> = {}
      for (const r of results) {
        if (r.status === 'fulfilled') map[r.value[0]] = r.value[1]
      }
      setLessonIndex((prev) => ({ ...prev, ...map }))
    })
    return () => {
      cancelled = true
    }
  }, [courses])

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
      .then(async (data) => {
        if (cancelled) return
        setLessonData(data)
        // 续播：优先选第一个「未学完且未锁定」的课时，学完则回第 1 节
        let resumeId: number | null = null
        try {
          const progress = await api<{
            lessons: { lesson_id: number; completed: boolean }[]
          }>(`/api/courses/${activeId}/progress`)
          if (cancelled) return
          const completed = new Set(
            progress.lessons.filter((x) => x.completed).map((x) => x.lesson_id),
          )
          resumeId =
            data.lessons.find((x) => !x.locked && !completed.has(x.id))?.id ??
            null
        } catch {
          // 进度接口失败不阻塞，退回默认选课逻辑
        }
        setActiveLessonId((current) => {
          const same = data.lessons.find((x) => x.id === current)
          if (same && !same.locked) return current
          return (
            resumeId ??
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

  // 课后小自测题库：一次拉全，按课时标题匹配
  useEffect(() => {
    void api<{ items: Record<string, LessonCheckItem> }>('/api/lesson-quiz')
      .then((d) => setChecks(d.items ?? {}))
      .catch(() => setChecks({}))
  }, [])

  // 切换课时时清空上一题的作答
  useEffect(() => {
    setCheckPick(null)
  }, [activeLessonId])

  const activeLesson = useMemo(
    () => lessonData?.lessons.find((x) => x.id === activeLessonId) ?? null,
    [lessonData, activeLessonId],
  )

  const activeCheck = activeLesson ? checks[activeLesson.title] ?? null : null

  const lessonPoints = useMemo(() => {
    const raw = activeLesson?.summary ?? ''
    return raw
      .split('\n')
      .map((line) => line.replace(/^[·•\-\s]+/, '').trim())
      .filter(Boolean)
  }, [activeLesson])

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

  /** 搜索结果：null 表示未搜索；命中时带上命中的课时标题（知识点） */
  const searchHits = useMemo(() => {
    const raw = keyword.trim()
    if (!raw) return null
    const terms = raw.split(/\s+/).map(normalize).filter(Boolean)
    if (!terms.length) return null
    const hits: { course: Course; lessons: string[] }[] = []
    for (const c of courses) {
      const lessons = lessonIndex[c.id] ?? []
      const base = normalize(
        [
          c.name,
          c.tagline ?? '',
          c.path_label ?? '',
          c.description ?? '',
          c.semester,
          c.teacher_name,
        ].join(' '),
      )
      const baseHit = terms.every((t) => base.includes(t))
      const hitLessons = lessons.filter((l) =>
        terms.some((t) => l.text.includes(t)),
      )
      if (!baseHit && hitLessons.length === 0) continue
      hits.push({
        course: c,
        lessons: [...new Set(hitLessons.map((l) => l.title))].slice(0, 2),
      })
    }
    return hits
  }, [keyword, courses, lessonIndex])

  const visibleCourses = useMemo(
    () => (searchHits ? searchHits.map((h) => h.course) : courses),
    [searchHits, courses],
  )

  const lessonHint = useMemo(() => {
    const map = new Map<number, string[]>()
    for (const h of searchHits ?? []) {
      if (h.lessons.length) map.set(h.course.id, h.lessons)
    }
    return map
  }, [searchHits])

  /** 当前详情只在「课程仍在可见列表里」时展示 */
  const activeVisible =
    !!active && visibleCourses.some((c) => c.id === active.id)

  // 搜索把当前选中的课程过滤掉时，自动落到第一个命中项
  useEffect(() => {
    if (!searchHits || searchHits.length === 0) return
    if (activeId != null && searchHits.some((h) => h.course.id === activeId)) {
      return
    }
    setActiveId(searchHits[0].course.id)
  }, [searchHits, activeId])

  function clearSearch() {
    setKeyword('')
  }

  function selectCourse(id: number) {
    setActiveId(id)
    setPayTip('')
    // 切换课程时清空测验状态
    setQuizOpen(false)
    setQuizQuestions([])
    setQuizAnswers({})
    setQuizResult(null)
    setQuizError('')
    setSearchParams(id ? { id: String(id) } : {})
  }

  async function openQuiz() {
    if (!active || quizLoading) return
    setQuizOpen(true)
    setQuizLoading(true)
    setQuizError('')
    try {
      const questions = await api<QuizQuestion[]>(
        `/api/courses/${active.id}/quiz`,
      )
      setQuizQuestions(questions)
      setQuizAnswers({})
      setQuizResult(null)
    } catch (e) {
      setQuizError(e instanceof Error ? e.message : '测验题加载失败')
    } finally {
      setQuizLoading(false)
    }
  }

  async function submitQuiz() {
    if (!active || quizSubmitting) return
    if (quizQuestions.some((q) => quizAnswers[q.id] == null)) {
      setQuizError('还有题目没作答，全部选完再交卷哦')
      return
    }
    setQuizSubmitting(true)
    setQuizError('')
    try {
      const result = await api<QuizResult>(`/api/courses/${active.id}/quiz`, {
        method: 'POST',
        body: JSON.stringify({ answers: quizAnswers }),
      })
      setQuizResult(result)
    } catch (e) {
      setQuizError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setQuizSubmitting(false)
    }
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

  function lessonNumber(id: number): number {
    const index = lessonData?.lessons.findIndex((x) => x.id === id) ?? -1
    return index >= 0 ? index + 1 : 0
  }

  function jumpToLesson(id: number) {
    const lesson = lessonData?.lessons.find((x) => x.id === id)
    if (!lesson || lesson.locked) return
    setActiveLessonId(id)
    window.setTimeout(() => {
      playerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 60)
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
          <div className="course-search">
            <div className="course-search-box">
              <input
                type="search"
                className="course-search-input"
                value={keyword}
                placeholder="输入课程关键词，如：氧疗、吸入药、急性加重"
                aria-label="搜索课程"
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') clearSearch()
                }}
              />
              {keyword ? (
                <button
                  type="button"
                  className="course-search-clear"
                  aria-label="清空搜索"
                  title="清空搜索"
                  onClick={clearSearch}
                >
                  ×
                </button>
              ) : null}
              <span className="course-search-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="18" height="18">
                  <circle
                    cx="11"
                    cy="11"
                    r="6.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M16 16l4.2 4.2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
            </div>
            <p className="course-search-hint">
              支持搜索课程名称、知识点关键词
              <Link to="/toolkit" className="course-search-tool">
                学习工具箱 ›
              </Link>
            </p>
          </div>

          {visibleCourses.length === 0 ? (
            <div className="course-search-empty">
              <p>没有找到与「{keyword.trim()}」相关的课程</p>
              <button type="button" className="btn small" onClick={clearSearch}>
                清空搜索
              </button>
            </div>
          ) : (
            <div className="course-card-grid">
              {visibleCourses.map((c) => (
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
                    {lessonHint.get(c.id)?.length ? (
                      <p className="meta course-card-hit">
                        命中知识点：{lessonHint.get(c.id)?.[0]}
                      </p>
                    ) : null}
                  </div>
                </button>
              ))}
            </div>
          )}

          {activeVisible && active && (
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

          {activeVisible && active && (
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
                  <div className="lesson-player-wrap" ref={playerRef}>
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

                  {activeLesson && !activeLesson.locked ? (
                    <div className="lesson-extra">
                      {lessonPoints.length ? (
                        <div className="lesson-points">
                          <strong>本节要点</strong>
                          <ul>
                            {lessonPoints.map((p) => (
                              <li key={p}>{p}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      <div className="lesson-check">
                        <div className="lesson-check-head">
                          <strong>课后小自测</strong>
                          <span className="meta">
                            1 题 · 即时判分，不影响学习进度
                          </span>
                        </div>
                        {activeCheck ? (
                          <>
                            <p className="lesson-check-q">
                              {activeCheck.question}
                            </p>
                            <div className="lesson-check-options">
                              {activeCheck.options.map((opt, i) => {
                                const answered = checkPick !== null
                                const isRight = answered && i === activeCheck.answer
                                const isWrong =
                                  answered && checkPick === i && i !== activeCheck.answer
                                return (
                                  <button
                                    key={opt}
                                    type="button"
                                    className={`lesson-check-option${isRight ? ' right' : ''}${
                                      isWrong ? ' wrong' : ''
                                    }`}
                                    disabled={answered}
                                    onClick={() => setCheckPick(i)}
                                  >
                                    <span className="opt-label">
                                      {OPTION_LABELS[i] ?? i + 1}
                                    </span>
                                    <span>{opt}</span>
                                  </button>
                                )
                              })}
                            </div>
                            {checkPick !== null ? (
                              <div className="lesson-check-result">
                                <p
                                  className={
                                    checkPick === activeCheck.answer
                                      ? 'ok-tip'
                                      : 'error'
                                  }
                                >
                                  {checkPick === activeCheck.answer
                                    ? '回答正确 ✓'
                                    : `正确答案：${
                                        OPTION_LABELS[activeCheck.answer]
                                      } · 再回看一遍上面的要点`}
                                </p>
                                {activeCheck.explanation ? (
                                  <p className="meta">
                                    解析：{activeCheck.explanation}
                                  </p>
                                ) : null}
                                <button
                                  type="button"
                                  className="linkish"
                                  onClick={() => setCheckPick(null)}
                                >
                                  再答一次
                                </button>
                              </div>
                            ) : null}
                          </>
                        ) : (
                          <p className="muted">
                            本节暂无自测题，先回顾上面的要点，学完标记即可。
                          </p>
                        )}
                      </div>
                    </div>
                  ) : null}
                </>
              )}
            </section>
          )}

          {lessonData &&
          lessonData.total_lessons > 0 &&
          lessonData.completed_lessons >= lessonData.total_lessons ? (
            <section className="item-card completion-card">
              <div className="completion-head">
                <span className="completion-badge">✓</span>
                <div>
                  <h2>恭喜完成本课程</h2>
                  <p className="meta">
                    已完成全部 {lessonData.total_lessons} 个课时，可以继续测验巩固，
                    或了解配套的健康服务。
                  </p>
                </div>
              </div>
              <div className="row-actions">
                <Link to="/service-shop" className="btn primary small">
                  了解相关服务
                </Link>
                <Link to="/symptom-diary" className="linkish">
                  记录症状
                </Link>
                <Link to="/reminders" className="linkish">
                  设置复查提醒
                </Link>
              </div>
            </section>
          ) : null}

          {activeVisible && (active?.enrolled || isAdmin) && (
            <section className="item-card quiz-section">
              <div className="lesson-head">
                <h3 className="section-label">板块测验</h3>
                {quizResult ? (
                  <span className="lesson-count">
                    得分 {quizResult.score}/{quizResult.total}
                  </span>
                ) : null}
              </div>

              {!quizOpen ? (
                <p className="muted" style={{ margin: 0 }}>
                  学完本课程后，来做几道题检验一下学习效果吧。
                  <button
                    type="button"
                    className="btn small"
                    style={{ marginLeft: 10 }}
                    onClick={() => void openQuiz()}
                  >
                    开始测验
                  </button>
                </p>
              ) : quizLoading ? (
                <p className="muted">题目加载中…</p>
              ) : quizError && quizQuestions.length === 0 ? (
                <p className="error">{quizError}</p>
              ) : quizQuestions.length === 0 ? (
                <p className="muted">该课程暂未配置测验题</p>
              ) : (
                <>
                  {quizError ? <p className="error">{quizError}</p> : null}
                  {quizResult ? (
                    <>
                      <p
                        className={
                          quizResult.score === quizResult.total
                            ? 'ok-tip'
                            : 'error'
                        }
                      >
                        {quizResult.score === quizResult.total
                          ? `🎉 全部答对！${quizResult.score}/${quizResult.total} 分`
                          : `本次得分 ${quizResult.score}/${quizResult.total}，错的题看下方解析回看课时。`}
                      </p>
                      <ul className="quiz-list">
                        {quizResult.details.map((d, i) => (
                          <li key={d.question_id} className="quiz-item">
                            <strong>
                              {i + 1}. {d.question}
                            </strong>
                            <p
                              className="meta"
                              style={{
                                color: d.correct ? '#2e7d32' : '#c62828',
                                margin: '4px 0',
                              }}
                            >
                              你的答案：
                              {d.chosen >= 0
                                ? OPTION_LABELS[d.chosen] ?? d.chosen
                                : '未答'}
                              {d.correct ? ' ✓ 正确' : ` ✗ 正确答案：${OPTION_LABELS[d.answer_index]}`}
                            </p>
                            {d.explanation ? (
                              <p className="meta" style={{ margin: 0 }}>
                                解析：{d.explanation}
                              </p>
                            ) : null}
                            {!d.correct && d.lesson_id ? (
                              <div className="row-actions">
                                <button
                                  type="button"
                                  className="linkish primary"
                                  disabled={
                                    !lessonData?.lessons.find(
                                      (x) => x.id === d.lesson_id && !x.locked,
                                    )
                                  }
                                  onClick={() => jumpToLesson(d.lesson_id as number)}
                                >
                                  回看第 {lessonNumber(d.lesson_id)} 课
                                  {d.lesson_title ? `：${d.lesson_title}` : ''}
                                </button>
                              </div>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                      <button
                        type="button"
                        className="btn small"
                        onClick={() => void openQuiz()}
                      >
                        重新测验
                      </button>
                    </>
                  ) : (
                    <>
                      <ul className="quiz-list">
                        {quizQuestions.map((q, qi) => (
                          <li key={q.id} className="quiz-item">
                            <strong>
                              {qi + 1}. {q.question}
                            </strong>
                            <div className="quiz-options">
                              {q.options.map((opt, oi) => (
                                <label
                                  key={oi}
                                  className={`quiz-option${
                                    quizAnswers[q.id] === oi ? ' active' : ''
                                  }`}
                                >
                                  <input
                                    type="radio"
                                    name={`quiz-${q.id}`}
                                    checked={quizAnswers[q.id] === oi}
                                    onChange={() =>
                                      setQuizAnswers((prev) => ({
                                        ...prev,
                                        [q.id]: oi,
                                      }))
                                    }
                                  />
                                  <span>
                                    {OPTION_LABELS[oi] ?? oi}. {opt}
                                  </span>
                                </label>
                              ))}
                            </div>
                          </li>
                        ))}
                      </ul>
                      <button
                        type="button"
                        className="btn primary small"
                        disabled={quizSubmitting}
                        onClick={() => void submitQuiz()}
                      >
                        {quizSubmitting ? '判分中…' : '交卷'}
                      </button>
                      <button
                        type="button"
                        className="btn small"
                        style={{ marginLeft: 8 }}
                        onClick={() => setQuizOpen(false)}
                      >
                        收起
                      </button>
                    </>
                  )}
                </>
              )}
            </section>
          )}

          {activeVisible && (active?.enrolled || isAdmin) && (
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
