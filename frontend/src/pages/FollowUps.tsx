import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { FollowUpPlan, FollowUpSummary, FollowUpVisit } from '../types'
import { formatDate, todayISO, offsetISO } from '../utils'

const STATE_LABEL: Record<string, string> = {
  overdue: '已逾期',
  due_soon: '即将到期',
  upcoming: '未到期',
  closed: '已结束',
}

const STATE_BADGE: Record<string, string> = {
  overdue: 'danger',
  due_soon: 'warn',
  upcoming: 'ok',
  closed: 'soft',
}

const PLAN_STATUS_LABEL: Record<string, string> = {
  active: '进行中',
  paused: '已暂停',
  closed: '已结束',
}

const TYPE_OPTIONS = [
  { value: 'outpatient', label: '门诊随访' },
  { value: 'lung_function', label: '肺功能复查' },
  { value: 'imaging', label: '影像复查' },
  { value: 'phone', label: '电话随访' },
  { value: 'other', label: '其他' },
]

/** 常见随访周期，点选即可，也可手动填天数 */
const INTERVAL_PRESETS = [
  { days: 30, label: '1 个月' },
  { days: 90, label: '3 个月' },
  { days: 180, label: '半年' },
  { days: 365, label: '1 年' },
]

function dueText(plan: FollowUpPlan): string {
  const n = plan.days_remaining
  if (plan.state === 'closed') return '已结束'
  if (n < 0) return `已逾期 ${Math.abs(n)} 天`
  if (n === 0) return '今天到期'
  if (n === 1) return '明天到期'
  return `还有 ${n} 天`
}

export default function FollowUps() {
  const [plans, setPlans] = useState<FollowUpPlan[]>([])
  const [summary, setSummary] = useState<FollowUpSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [followType, setFollowType] = useState('outpatient')
  const [intervalDays, setIntervalDays] = useState(90)
  const [nextDue, setNextDue] = useState(offsetISO(90))
  const [hospital, setHospital] = useState('')
  const [doctor, setDoctor] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  // 完成随访：按计划展开填写
  const [completingId, setCompletingId] = useState<number | null>(null)
  const [visitDate, setVisitDate] = useState(todayISO())
  const [visitResult, setVisitResult] = useState('')
  const [completing, setCompleting] = useState(false)

  // 随访记录展开
  const [visitsOf, setVisitsOf] = useState<number | null>(null)
  const [visits, setVisits] = useState<FollowUpVisit[]>([])

  async function loadAll() {
    try {
      const [p, s] = await Promise.all([
        api<FollowUpPlan[]>('/api/followups?include_closed=true'),
        api<FollowUpSummary>('/api/followups/summary'),
      ])
      setPlans(p)
      setSummary(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
  }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setTip('')
    try {
      await api<FollowUpPlan>('/api/followups', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          follow_type: followType,
          interval_days: intervalDays,
          next_due_date: nextDue,
          hospital: hospital.trim(),
          doctor: doctor.trim(),
          note: note.trim(),
        }),
      })
      setTip('随访计划已创建，到期前会自动提醒')
      setShowForm(false)
      setTitle('')
      setFollowType('outpatient')
      setIntervalDays(90)
      setNextDue(offsetISO(90))
      setHospital('')
      setDoctor('')
      setNote('')
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setSaving(false)
    }
  }

  async function onComplete(plan: FollowUpPlan) {
    setCompleting(true)
    setError('')
    try {
      const updated = await api<FollowUpPlan>(`/api/followups/${plan.id}/complete`, {
        method: 'POST',
        body: JSON.stringify({
          visit_date: visitDate,
          result: visitResult.trim(),
        }),
      })
      setTip(`已记录随访，下次到期 ${formatDate(updated.next_due_date)}`)
      setCompletingId(null)
      setVisitResult('')
      setVisitDate(todayISO())
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败')
    } finally {
      setCompleting(false)
    }
  }

  async function togglePlan(plan: FollowUpPlan) {
    const next = plan.status === 'active' ? 'paused' : 'active'
    setError('')
    try {
      await api(`/api/followups/${plan.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: next }),
      })
      setTip(next === 'paused' ? '已暂停，将停止提醒' : '已恢复提醒')
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    }
  }

  async function removePlan(plan: FollowUpPlan) {
    if (!confirm(`删除「${plan.title}」及其随访记录？`)) return
    setError('')
    try {
      await api(`/api/followups/${plan.id}`, { method: 'DELETE' })
      setTip('已删除')
      if (visitsOf === plan.id) setVisitsOf(null)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  async function toggleVisits(plan: FollowUpPlan) {
    if (visitsOf === plan.id) {
      setVisitsOf(null)
      setVisits([])
      return
    }
    setError('')
    try {
      const list = await api<FollowUpVisit[]>(`/api/followups/${plan.id}/visits`)
      setVisits(list)
      setVisitsOf(plan.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    }
  }

  return (
    <div className="screen stack-gap">
      <Link to="/supervision" className="back-link">
        ← 返回监督
      </Link>
      <div className="page-title">
        <div>
          <h1>随访提醒</h1>
          <p className="sub">按周期提醒复查，完成后自动排下一次</p>
        </div>
        <div className="page-title-actions-only">
          <Link to="/supervision/symptom-diary" className="linkish">
            症状日记 ›
          </Link>
          <Link to="/supervision/medication" className="linkish">
            用药打卡 ›
          </Link>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {tip ? <p className="ok-tip">{tip}</p> : null}

      {summary ? (
        <section className="form-card">
          <h2>随访概览</h2>
          <div className="stat-grid">
            <div className="stat-cell">
              <strong>{summary.overdue}</strong>
              <span>已逾期</span>
            </div>
            <div className="stat-cell">
              <strong>{summary.due_soon}</strong>
              <span>7 天内</span>
            </div>
            <div className="stat-cell">
              <strong>{summary.visit_count}</strong>
              <span>已完成随访</span>
            </div>
            <div className="stat-cell">
              <strong>{summary.active}</strong>
              <span>进行中</span>
            </div>
          </div>
          {summary.next_due_date ? (
            <p className="meta">
              下次随访：{summary.next_title} · {formatDate(summary.next_due_date)}
            </p>
          ) : (
            <p className="meta">暂无进行中的随访计划</p>
          )}
        </section>
      ) : null}

      {summary?.overdue ? (
        <div className="symptom-warning">
          <strong>有 {summary.overdue} 项随访已逾期</strong>
          <p>建议尽快联系医生补约；如近期症状明显加重，不必等到随访日，提前就诊。</p>
        </div>
      ) : null}

      <section>
        <div className="section-head-row">
          <h3 className="section-label">随访计划</h3>
          <button type="button" className="btn-add" onClick={() => setShowForm((v) => !v)}>
            {showForm ? '收起' : '+ 添加'}
          </button>
        </div>

        {showForm ? (
          <form className="form-card" onSubmit={onCreate}>
            <h2>添加随访计划</h2>
            <label>
              标题
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="如：呼吸科门诊随访"
                maxLength={200}
                required
              />
            </label>
            <label>
              类型
              <select value={followType} onChange={(e) => setFollowType(e.target.value)}>
                {TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              随访周期
              <div className="chip-row">
                {INTERVAL_PRESETS.map((p) => (
                  <button
                    key={p.days}
                    type="button"
                    className={`chip${intervalDays === p.days ? ' active' : ''}`}
                    onClick={() => {
                      setIntervalDays(p.days)
                      setNextDue(offsetISO(p.days))
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </label>
            <label>
              周期天数
              <input
                type="number"
                min={7}
                max={730}
                value={intervalDays}
                onChange={(e) => setIntervalDays(Number(e.target.value) || 90)}
                required
              />
            </label>
            <label>
              下次到期日
              <input
                type="date"
                value={nextDue}
                onChange={(e) => setNextDue(e.target.value || nextDue)}
                required
              />
            </label>
            <label>
              医院（可选）
              <input
                value={hospital}
                onChange={(e) => setHospital(e.target.value)}
                placeholder="如：市第一医院"
                maxLength={120}
              />
            </label>
            <label>
              医生（可选）
              <input
                value={doctor}
                onChange={(e) => setDoctor(e.target.value)}
                placeholder="如：张医生"
                maxLength={60}
              />
            </label>
            <label>
              备注（可选）
              <textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="如：带肺功能报告与用药清单"
                maxLength={2000}
              />
            </label>
            <button className="btn primary block" type="submit" disabled={saving}>
              {saving ? '保存中…' : '保存计划'}
            </button>
          </form>
        ) : null}

        {loading ? (
          <p className="muted">加载中…</p>
        ) : plans.length === 0 ? (
          <p className="muted">还没有随访计划。添加后会在到期前 7 天、1 天和当天提醒你。</p>
        ) : (
          <ul className="list-card">
            {plans.map((p) => (
              <li key={p.id}>
                <h3>
                  {p.title}
                  <span className={`badge ${STATE_BADGE[p.state] ?? 'soft'}`}>
                    {STATE_LABEL[p.state] ?? p.state}
                  </span>
                </h3>
                <p className="meta">
                  {p.follow_type_label} · 每 {p.interval_days} 天 · {dueText(p)}
                </p>
                <p className="meta">
                  下次到期 {formatDate(p.next_due_date)}
                  {p.last_visit_date ? ` · 上次随访 ${formatDate(p.last_visit_date)}` : ''}
                </p>
                {p.hospital || p.doctor ? (
                  <p className="meta">
                    {[p.hospital, p.doctor ? `${p.doctor} 医生` : ''].filter(Boolean).join(' · ')}
                  </p>
                ) : null}
                {p.status !== 'active' ? (
                  <p className="meta">状态：{PLAN_STATUS_LABEL[p.status] ?? p.status}</p>
                ) : null}
                {p.note ? <p style={{ margin: '6px 0 0' }}>{p.note}</p> : null}

                <div className="row-actions">
                  {p.status === 'active' ? (
                    <button
                      type="button"
                      className="linkish primary"
                      onClick={() => {
                        setCompletingId(completingId === p.id ? null : p.id)
                        setVisitDate(todayISO())
                        setVisitResult('')
                      }}
                    >
                      完成随访
                    </button>
                  ) : null}
                  {p.visit_count > 0 ? (
                    <button type="button" className="linkish" onClick={() => void toggleVisits(p)}>
                      {visitsOf === p.id ? '收起记录' : `随访记录（${p.visit_count}）`}
                    </button>
                  ) : null}
                  {p.status !== 'closed' ? (
                    <button type="button" className="linkish" onClick={() => void togglePlan(p)}>
                      {p.status === 'active' ? '暂停' : '恢复'}
                    </button>
                  ) : null}
                  <button type="button" className="linkish" onClick={() => void removePlan(p)}>
                    删除
                  </button>
                </div>

                {completingId === p.id ? (
                  <div className="fu-complete">
                    <label>
                      随访日期
                      <input
                        type="date"
                        value={visitDate}
                        max={todayISO()}
                        onChange={(e) => setVisitDate(e.target.value || todayISO())}
                      />
                    </label>
                    <label>
                      结果 / 备注（可选）
                      <textarea
                        rows={2}
                        value={visitResult}
                        onChange={(e) => setVisitResult(e.target.value)}
                        placeholder="如：症状稳定，继续原方案"
                        maxLength={2000}
                      />
                    </label>
                    <p className="meta">
                      提交后按每 {p.interval_days} 天排下一次随访，并停止本轮提醒。
                    </p>
                    <button
                      className="btn primary block"
                      type="button"
                      disabled={completing}
                      onClick={() => void onComplete(p)}
                    >
                      {completing ? '提交中…' : '确认完成'}
                    </button>
                  </div>
                ) : null}

                {visitsOf === p.id ? (
                  <ul className="fu-visits">
                    {visits.length === 0 ? (
                      <li className="meta">暂无记录</li>
                    ) : (
                      visits.map((v) => (
                        <li key={v.id}>
                          <strong>{formatDate(v.visit_date)}</strong>
                          <span className="meta"> · 下次 {formatDate(v.next_due_date)}</span>
                          {v.result ? <p style={{ margin: '4px 0 0' }}>{v.result}</p> : null}
                        </li>
                      ))
                    )}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {summary?.disclaimer ? <p className="mall-footnote">{summary.disclaimer}</p> : null}
      </section>
    </div>
  )
}
