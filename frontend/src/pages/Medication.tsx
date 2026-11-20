import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type {
  MedicationAdherence,
  MedicationLog,
  MedicationPlan,
  MedicationSlot,
  MedicationToday,
} from '../types'
import { formatDate, formatDateTime, todayISO } from '../utils'

const STATUS_LABEL: Record<string, string> = {
  pending: '待打卡',
  taken: '已服用',
  skipped: '已跳过',
}

const PLAN_STATUS_LABEL: Record<string, string> = {
  active: '进行中',
  paused: '已暂停',
  archived: '已停用',
}

const FREQUENCY_OPTIONS = [1, 2, 3, 4, 5, 6]

export default function Medication() {
  const [today, setToday] = useState<MedicationToday | null>(null)
  const [plans, setPlans] = useState<MedicationPlan[]>([])
  const [adh, setAdh] = useState<MedicationAdherence | null>(null)
  const [logs, setLogs] = useState<MedicationLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')
  const [busyId, setBusyId] = useState<string>('')

  // 新建计划表单
  const [showForm, setShowForm] = useState(false)
  const [drugName, setDrugName] = useState('')
  const [dosage, setDosage] = useState('')
  const [frequency, setFrequency] = useState(2)
  const [times, setTimes] = useState('08:00,20:00')
  const [startDate, setStartDate] = useState(todayISO())
  const [endDate, setEndDate] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  async function loadAll() {
    try {
      const [t, p, a, l] = await Promise.all([
        api<MedicationToday>('/api/medication/today'),
        api<MedicationPlan[]>('/api/medication/plans'),
        api<MedicationAdherence>('/api/medication/adherence?days=30'),
        api<MedicationLog[]>('/api/medication/logs?days=14'),
      ])
      setToday(t)
      setPlans(p)
      setAdh(a)
      setLogs(l)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
  }, [])

  async function checkIn(slot: MedicationSlot, status: 'taken' | 'skipped' | 'pending') {
    const key = `${slot.plan_id}-${slot.slot}`
    setBusyId(key)
    setError('')
    try {
      await api<MedicationSlot>('/api/medication/checkin', {
        method: 'POST',
        body: JSON.stringify({
          plan_id: slot.plan_id,
          take_date: slot.take_date,
          slot: slot.slot,
          status,
        }),
      })
      if (status === 'taken') setTip(`已记录：${slot.drug_name} 第 ${slot.slot} 次`)
      else if (status === 'skipped') setTip(`已跳过：${slot.drug_name} 第 ${slot.slot} 次`)
      else setTip('已撤销本次打卡')
      await loadAll()
    } catch (e) {
      setError(e instanceof Error ? e.message : '打卡失败')
    } finally {
      setBusyId('')
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setTip('')
    try {
      await api<MedicationPlan>('/api/medication/plans', {
        method: 'POST',
        body: JSON.stringify({
          drug_name: drugName.trim(),
          dosage: dosage.trim(),
          frequency,
          times: times.trim(),
          start_date: startDate,
          end_date: endDate || null,
          note: note.trim(),
        }),
      })
      setTip('用药计划已创建')
      setShowForm(false)
      setDrugName('')
      setDosage('')
      setFrequency(2)
      setTimes('08:00,20:00')
      setStartDate(todayISO())
      setEndDate('')
      setNote('')
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setSaving(false)
    }
  }

  async function togglePlan(plan: MedicationPlan) {
    const next = plan.status === 'active' ? 'paused' : 'active'
    setError('')
    try {
      await api(`/api/medication/plans/${plan.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: next }),
      })
      setTip(next === 'paused' ? '计划已暂停' : '计划已恢复')
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    }
  }

  async function removePlan(plan: MedicationPlan) {
    if (!confirm(`删除「${plan.drug_name}」及其全部打卡记录？`)) return
    setError('')
    try {
      await api(`/api/medication/plans/${plan.id}`, { method: 'DELETE' })
      setTip('计划已删除')
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  const done = today ? today.taken + today.skipped : 0
  const percent = today && today.total > 0 ? Math.round((done / today.total) * 100) : 0

  return (
    <div className="screen stack-gap">
      <Link to="/supervision" className="back-link">
        ← 返回监督
      </Link>
      <div className="page-title">
        <div>
          <h1>用药打卡</h1>
          <p className="sub">每天按时打卡，复诊时把记录给医生看</p>
        </div>
        <div className="page-title-actions-only">
          <Link to="/supervision/symptom-diary" className="linkish">
            症状日记 ›
          </Link>
          <Link to="/supervision/followups" className="linkish">
            随访提醒 ›
          </Link>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {tip ? <p className="ok-tip">{tip}</p> : null}

      <section className="form-card">
        <h2>今日打卡</h2>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : !today || today.items.length === 0 ? (
          <p className="muted">
            今天没有待打卡的用药。可在下方「我的用药计划」中添加，或确认计划是否处于进行中。
          </p>
        ) : (
          <>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${percent}%` }} />
            </div>
            <p className="meta">
              已完成 {done} / {today.total} 次 · 待打卡 {today.pending} 次
              {today.skipped > 0 ? ` · 已跳过 ${today.skipped} 次` : ''}
            </p>
            <ul className="med-slots">
              {today.items.map((s) => {
                const key = `${s.plan_id}-${s.slot}`
                return (
                  <li key={key} className={`med-slot status-${s.status}`}>
                    <span className="med-time">{s.scheduled_time || '—'}</span>
                    <div className="med-slot-main">
                      <strong>{s.drug_name}</strong>
                      <p className="meta">
                        {s.dosage ? `${s.dosage} · ` : ''}第 {s.slot} 次
                      </p>
                    </div>
                    <span
                      className={`badge ${
                        s.status === 'taken' ? 'ok' : s.status === 'skipped' ? 'soft' : ''
                      }`}
                    >
                      {STATUS_LABEL[s.status] ?? s.status}
                    </span>
                    <div className="row-actions">
                      {s.status !== 'taken' ? (
                        <button
                          type="button"
                          className="linkish primary"
                          disabled={busyId === key}
                          onClick={() => void checkIn(s, 'taken')}
                        >
                          已服用
                        </button>
                      ) : null}
                      {s.status !== 'skipped' ? (
                        <button
                          type="button"
                          className="linkish"
                          disabled={busyId === key}
                          onClick={() => void checkIn(s, 'skipped')}
                        >
                          跳过
                        </button>
                      ) : null}
                      {s.status !== 'pending' ? (
                        <button
                          type="button"
                          className="linkish"
                          disabled={busyId === key}
                          onClick={() => void checkIn(s, 'pending')}
                        >
                          撤销
                        </button>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ul>
          </>
        )}
      </section>

      {adh ? (
        <section className="form-card">
          <h2>近 30 天依从率</h2>
          <div className="stat-grid">
            <div className="stat-cell">
              <strong>{adh.rate}%</strong>
              <span>依从率</span>
            </div>
            <div className="stat-cell">
              <strong>{adh.streak_days}</strong>
              <span>连续达标（天）</span>
            </div>
            <div className="stat-cell">
              <strong>{adh.taken}</strong>
              <span>已服用</span>
            </div>
            <div className="stat-cell">
              <strong>{adh.missed}</strong>
              <span>漏服</span>
            </div>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${Math.min(100, adh.rate)}%` }} />
          </div>
          <p className="meta">
            应服 {adh.scheduled} 次 · 跳过 {adh.skipped} 次 · {adh.from_date} 至 {adh.to_date}
            {adh.missed > 0 ? ' · 漏服按「应服 − 已服 − 已跳过」统计' : ''}
          </p>
        </section>
      ) : null}

      <section>
        <div className="section-head-row">
          <h3 className="section-label">我的用药计划</h3>
          <button type="button" className="btn-add" onClick={() => setShowForm((v) => !v)}>
            {showForm ? '收起' : '+ 添加'}
          </button>
        </div>

        {showForm ? (
          <form className="form-card" onSubmit={onCreate}>
            <h2>添加用药计划</h2>
            <label>
              药名
              <input
                value={drugName}
                onChange={(e) => setDrugName(e.target.value)}
                placeholder="如：布地奈德福莫特罗吸入剂"
                maxLength={120}
                required
              />
            </label>
            <label>
              剂量 / 用法
              <input
                value={dosage}
                onChange={(e) => setDosage(e.target.value)}
                placeholder="如：每次 1 吸"
                maxLength={120}
              />
            </label>
            <label>
              每日次数
              <div className="chip-row">
                {FREQUENCY_OPTIONS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={`chip${frequency === n ? ' active' : ''}`}
                    onClick={() => setFrequency(n)}
                  >
                    {n} 次
                  </button>
                ))}
              </div>
            </label>
            <label>
              服用时间（逗号分隔，可留空）
              <input
                value={times}
                onChange={(e) => setTimes(e.target.value)}
                placeholder="08:00,20:00"
                maxLength={200}
              />
            </label>
            <label>
              开始日期
              <input
                type="date"
                value={startDate}
                max={todayISO()}
                onChange={(e) => setStartDate(e.target.value || todayISO())}
                required
              />
            </label>
            <label>
              结束日期（留空表示长期服用）
              <input
                type="date"
                value={endDate}
                min={startDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </label>
            <label>
              备注（可选）
              <textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="如：吸入后漱口"
                maxLength={2000}
              />
            </label>
            <button className="btn primary block" type="submit" disabled={saving}>
              {saving ? '保存中…' : '保存计划'}
            </button>
          </form>
        ) : null}

        {plans.length === 0 ? (
          <p className="muted">还没有用药计划。</p>
        ) : (
          <ul className="list-card">
            {plans.map((p) => (
              <li key={p.id}>
                <h3>
                  {p.drug_name}
                  <span
                    className={`badge ${p.status === 'active' ? 'ok' : 'soft'}`}
                  >
                    {PLAN_STATUS_LABEL[p.status] ?? p.status}
                  </span>
                </h3>
                <p className="meta">
                  {p.dosage ? `${p.dosage} · ` : ''}每日 {p.frequency} 次
                  {p.times ? ` · ${p.times}` : ''}
                </p>
                <p className="meta">
                  {formatDate(p.start_date)} 起
                  {p.end_date ? ` 至 ${formatDate(p.end_date)}` : ' · 长期'}
                </p>
                {p.note ? <p style={{ margin: '6px 0 0' }}>{p.note}</p> : null}
                <div className="row-actions">
                  <button type="button" className="linkish" onClick={() => void togglePlan(p)}>
                    {p.status === 'active' ? '暂停' : '恢复'}
                  </button>
                  <button type="button" className="linkish" onClick={() => void removePlan(p)}>
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="section-label">近 14 天打卡记录</h3>
        {logs.length === 0 ? (
          <p className="muted">还没有打卡记录。</p>
        ) : (
          <ul className="list-card">
            {logs.slice(0, 20).map((l) => (
              <li key={l.id}>
                <h3>
                  {l.drug_name}
                  <span className={`badge ${l.status === 'taken' ? 'ok' : 'soft'}`}>
                    {STATUS_LABEL[l.status] ?? l.status}
                  </span>
                </h3>
                <p className="meta">
                  {formatDate(l.take_date)} · 第 {l.slot} 次
                  {l.scheduled_time ? ` · ${l.scheduled_time}` : ''}
                  {l.checked_at ? ` · 打卡于 ${formatDateTime(l.checked_at)}` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
        {today?.disclaimer ? <p className="mall-footnote">{today.disclaimer}</p> : null}
      </section>
    </div>
  )
}
