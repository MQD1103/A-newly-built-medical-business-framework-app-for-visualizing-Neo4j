import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { FollowUpSummary, MedicationToday, SymptomDiary } from '../types'
import { formatDate } from '../utils'

function IconDiary() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm3 5h6M9 12h6M9 16h3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconPill() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M10.5 4.5a4.2 4.2 0 0 1 6 0l3 3a4.2 4.2 0 0 1 0 6l-6 6a4.2 4.2 0 0 1-6 0l-3-3a4.2 4.2 0 0 1 0-6ZM8.4 8.6l7 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconCalendar() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M4 6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5v13A1.5 1.5 0 0 1 18.5 21h-13A1.5 1.5 0 0 1 4 19.5Zm4-3v3m8-3v3M4 10h16m-9.5 4.5L13 17l3.5-3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** 监督板块承载的三项自我管理功能，状态行来自各自后端接口的实时汇总 */
const items = [
  {
    to: '/supervision/symptom-diary',
    title: '症状日记',
    desc: '记录咳嗽、气促与痰量变化，观察趋势',
    key: 'symptom' as const,
    Icon: IconDiary,
  },
  {
    to: '/supervision/medication',
    title: '用药打卡',
    desc: '每日班次打卡，自动生成依从率回顾',
    key: 'medication' as const,
    Icon: IconPill,
  },
  {
    to: '/supervision/followups',
    title: '随访提醒',
    desc: '按周期提醒复查，完成后自动排下一次',
    key: 'followup' as const,
    Icon: IconCalendar,
  },
]

export default function Supervision() {
  const [diary, setDiary] = useState<SymptomDiary | null>(null)
  const [today, setToday] = useState<MedicationToday | null>(null)
  const [fu, setFu] = useState<FollowUpSummary | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api<SymptomDiary>('/api/symptoms?days=7'),
      api<MedicationToday>('/api/medication/today'),
      api<FollowUpSummary>('/api/followups/summary'),
    ])
      .then(([d, t, f]) => {
        if (cancelled) return
        setDiary(d)
        setToday(t)
        setFu(f)
      })
      .catch(() => {
        // 概览只是辅助信息，取不到不影响三张入口卡可用
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  /** 每张卡片下面那行实时状态 */
  function statusText(key: 'symptom' | 'medication' | 'followup'): string {
    if (failed) return '暂无数据'
    if (key === 'symptom') {
      if (!diary) return '加载中…'
      const dates = diary.items.map((i) => i.record_date)
      if (dates.length === 0) return '近 7 天还没有记录'
      const last = dates.reduce((a, b) => (a > b ? a : b))
      return `近 7 天已记 ${dates.length} 条 · 最近 ${formatDate(last)}`
    }
    if (key === 'medication') {
      if (!today) return '加载中…'
      if (today.total === 0) return '还没有用药计划'
      return `今日 ${today.taken}/${today.total} 已服 · 待打卡 ${today.pending}`
    }
    if (!fu) return '加载中…'
    if (fu.overdue > 0) return `${fu.overdue} 项已逾期，请尽快补约`
    if (fu.next_due_date) return `下次 ${formatDate(fu.next_due_date)} · ${fu.next_title}`
    return '暂无进行中的随访计划'
  }

  /** 顶部提醒：把最需要处理的一件事顶到最前面 */
  const alerts: string[] = []
  if (fu && fu.overdue > 0) alerts.push(`有 ${fu.overdue} 项随访已逾期，请尽快联系医生补约。`)
  if (today && today.pending > 0) alerts.push(`今天还有 ${today.pending} 次用药没打卡。`)
  if (diary?.warning && diary.warning_text) alerts.push(diary.warning_text)

  return (
    <div className="screen stack-gap">
      <Link to="/mall" className="back-link">
        ← 返回商城
      </Link>
      <div className="page-title">
        <div>
          <h1>监督</h1>
          <p className="sub">症状 · 用药 · 随访，三项日常自我管理</p>
        </div>
      </div>

      {alerts.length > 0 ? (
        <div className="supervision-alert">
          <strong>需要关注</strong>
          <ul>
            {alerts.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="supervision-stats">
        <div>
          <strong>{today ? `${today.taken}/${today.total}` : '—'}</strong>
          <span>今日已服药</span>
        </div>
        <div>
          <strong>{fu ? fu.overdue : '—'}</strong>
          <span>随访逾期</span>
        </div>
        <div>
          <strong>
            {diary ? diary.items.length : '—'}
          </strong>
          <span>近 7 天记录</span>
        </div>
      </section>

      <div className="hub-grid">
        {items.map((it) => (
          <Link key={it.to} to={it.to} className="hub-card tone-a">
            <div className="hub-card-top">
              <span className="hub-card-icon">
                <it.Icon />
              </span>
              <strong>{it.title}</strong>
            </div>
            <p>{it.desc}</p>
            <p className="supervision-status">{statusText(it.key)}</p>
            <span className="hub-go">进入 ›</span>
          </Link>
        ))}
      </div>

      <p className="mall-footnote">
        记录仅用于自我观察与复诊参考，不能替代医生诊断；如症状明显加重请及时就医。
      </p>
    </div>
  )
}
