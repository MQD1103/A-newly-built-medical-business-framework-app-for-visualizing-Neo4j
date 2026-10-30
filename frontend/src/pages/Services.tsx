import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Reminder, ScheduleSlot } from '../types'
import { formatDateTime, weekdayLabel } from '../utils'

const entries = [
  {
    to: '/schedule',
    icon: '🗓️',
    title: '课表',
    desc: '按周查看课程安排，每天上几节一目了然',
    tag: '本周课表',
    tone: 'a' as const,
  },
  {
    to: '/reminders',
    icon: '⏰',
    title: '提醒',
    desc: '个人与管理提醒、截止倒计时，重要事项不遗漏',
    tag: '待办提醒',
    tone: 'b' as const,
  },
  {
    to: '/linked',
    icon: '🔗',
    title: '关联信息',
    desc: '家人、医院与课程关联，联系人一站式管理',
    tag: '信息关联',
    tone: 'c' as const,
  },
]

export default function Services() {
  const [slots, setSlots] = useState<ScheduleSlot[]>([])
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [familyCount, setFamilyCount] = useState<number | null>(null)
  const [quickTitle, setQuickTitle] = useState('')
  // 默认时间：一小时后整点，免去手动选择
  const [quickTime, setQuickTime] = useState(() => {
    const d = new Date(Date.now() + 3600_000)
    d.setMinutes(0, 0, 0)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`
  })
  const [quickBusy, setQuickBusy] = useState(false)
  const [quickMsg, setQuickMsg] = useState('')

  // 每日健康打卡（本地记录 + 连续天数）
  const [checkins, setCheckins] = useState<{ date: string; mood: string }[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('svc-checkins') || '[]')
    } catch {
      return []
    }
  })
  const fmtDate = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const todayStr = fmtDate(new Date())
  const todayCheckin = checkins.find((c) => c.date === todayStr)
  const streak = useMemo(() => {
    const set = new Set(checkins.map((c) => c.date))
    const d = new Date()
    if (!set.has(fmtDate(d))) d.setDate(d.getDate() - 1)
    let n = 0
    while (set.has(fmtDate(d))) {
      n += 1
      d.setDate(d.getDate() - 1)
    }
    return n
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkins])

  function doCheckin(mood: string) {
    if (todayCheckin) return
    const next = [...checkins, { date: todayStr, mood }]
    setCheckins(next)
    localStorage.setItem('svc-checkins', JSON.stringify(next))
  }

  async function load() {
    try {
      const [s, r, f] = await Promise.all([
        api<ScheduleSlot[]>('/api/schedule/slots'),
        api<Reminder[]>('/api/reminders'),
        api<unknown[]>('/api/links/family'),
      ])
      setSlots(s)
      setReminders(r)
      setFamilyCount(f.length)
    } catch {
      // 概览数据加载失败不影响入口使用
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const todayIdx = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1
  const nowHM = new Date().toTimeString().slice(0, 5)

  const todaySlots = useMemo(
    () =>
      slots
        .filter((s) => s.weekday === todayIdx)
        .sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [slots, todayIdx],
  )
  const nextSlot = todaySlots.find((s) => s.start_time >= nowHM) ?? todaySlots[0]

  const pending = useMemo(
    () => reminders.filter((r) => r.status === 'pending'),
    [reminders],
  )
  const nextReminder = useMemo(
    () =>
      pending
        .slice()
        .sort((a, b) => a.due_at.localeCompare(b.due_at))[0] ?? null,
    [pending],
  )

  async function quickAdd(e: FormEvent) {
    e.preventDefault()
    if (!quickTitle.trim() || !quickTime || quickBusy) return
    setQuickBusy(true)
    setQuickMsg('')
    try {
      await api('/api/reminders', {
        method: 'POST',
        body: JSON.stringify({
          title: quickTitle.trim(),
          due_at: new Date(quickTime).toISOString(),
        }),
      })
      setQuickMsg('✅ 提醒已创建，到点会提醒你')
      setQuickTitle('')
      setQuickTime('')
      await load()
    } catch (err) {
      setQuickMsg(`❌ ${err instanceof Error ? err.message : '添加失败，请稍后重试'}`)
    } finally {
      setQuickBusy(false)
    }
  }

  return (
    <div className="screen stack-gap svc-screen">
      <section className="svc-hero">
        <div className="svc-hero-glow" aria-hidden="true" />
        <div className="svc-hero-inner">
          <span className="svc-hero-badge">服务中心</span>
          <h1>贴心服务 · 伴你康复</h1>
          <p className="svc-hero-sub">课表 · 提醒 · 关联信息，一个入口全搞定</p>
        </div>
      </section>

      {/* 今日概览：真实数据速览 */}
      <section className="svc-today">
        <div className="svc-today-head">
          <h2>📋 今日概览</h2>
          <span className="svc-today-date">{weekdayLabel(todayIdx)}</span>
        </div>
        <div className="svc-today-grid">
          <Link to="/schedule" className="svc-stat">
            <span className="svc-stat-num">{todaySlots.length}</span>
            <span className="svc-stat-label">今日课程</span>
            <span className="svc-stat-sub">
              {nextSlot ? `${nextSlot.start_time} ${nextSlot.course_name}` : '今天没有课'}
            </span>
          </Link>
          <Link to="/reminders" className="svc-stat">
            <span className="svc-stat-num">{pending.length}</span>
            <span className="svc-stat-label">待办提醒</span>
            <span className="svc-stat-sub">
              {nextReminder
                ? `${nextReminder.title} · ${formatDateTime(nextReminder.due_at)}`
                : '暂无待办'}
            </span>
          </Link>
          <Link to="/linked" className="svc-stat">
            <span className="svc-stat-num">{familyCount ?? '-'}</span>
            <span className="svc-stat-label">关联家人</span>
            <span className="svc-stat-sub">
              {familyCount ? '紧急时可一键联系' : '去添加家人'}
            </span>
          </Link>
        </div>
      </section>

      {/* 快捷提醒：一句话 + 时间，立即创建 */}
      <section className="svc-quick">
        <h2>⏰ 快捷提醒</h2>
        <p className="svc-quick-tip">服药、复诊、喝水… 一句话加个时间，到点提醒你</p>
        <form className="svc-quick-form" onSubmit={quickAdd}>
          <input
            value={quickTitle}
            onChange={(e) => setQuickTitle(e.target.value)}
            placeholder="提醒事项，如：晚上吃布地奈德"
            maxLength={60}
          />
          <input
            type="datetime-local"
            value={quickTime}
            onChange={(e) => setQuickTime(e.target.value)}
            required
          />
          <button
            type="submit"
            className="btn small primary"
            disabled={quickBusy || !quickTitle.trim() || !quickTime}
          >
            {quickBusy ? '添加中…' : '添加'}
          </button>
        </form>
        {quickMsg && (
          <p className={`mall-modal-msg ${quickMsg.startsWith('✅') ? 'ok' : 'err'}`}>{quickMsg}</p>
        )}
      </section>

      {/* 每日健康打卡 */}
      <section className="svc-checkin">
        <h2>🌤️ 每日健康打卡</h2>
        {todayCheckin ? (
          <div className="svc-checkin-done">
            <span className="svc-checkin-mood">
              {todayCheckin.mood === 'good' ? '😊' : todayCheckin.mood === 'ok' ? '😐' : '😟'}
            </span>
            <div>
              <p className="svc-checkin-text">今天已打卡，连续打卡 <strong>{streak}</strong> 天</p>
              <p className="svc-checkin-sub">坚持记录身体状况，康复更有数</p>
            </div>
          </div>
        ) : (
          <div className="svc-checkin-row">
            <span className="svc-checkin-ask">今天感觉怎么样？</span>
            <button type="button" className="svc-mood" onClick={() => doCheckin('good')}>😊 不错</button>
            <button type="button" className="svc-mood" onClick={() => doCheckin('ok')}>😐 一般</button>
            <button type="button" className="svc-mood" onClick={() => doCheckin('bad')}>😟 不太好</button>
          </div>
        )}
      </section>

      <div className="svc-grid">
        {entries.map((e) => (
          <Link key={e.to} to={e.to} className={`svc-card svc-tone-${e.tone}`}>
            <div className="svc-card-icon" aria-hidden="true">{e.icon}</div>
            <div className="svc-card-body">
              <div className="svc-card-top">
                <strong>{e.title}</strong>
                <span className="svc-card-tag">{e.tag}</span>
              </div>
              <p>{e.desc}</p>
            </div>
            <span className="svc-card-go">进入 →</span>
          </Link>
        ))}
      </div>

      <p className="svc-footnote">更多健康服务持续接入中</p>
    </div>
  )
}