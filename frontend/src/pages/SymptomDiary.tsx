import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { SymptomDiary, SymptomEntry } from '../types'
import { formatDate, formatDateTime } from '../utils'

const SCALE_LABELS = ['无', '轻', '中', '重']

const METRICS = [
  { key: 'cough', label: '咳嗽' },
  { key: 'dyspnea', label: '气短' },
  { key: 'sputum', label: '痰量' },
] as const

type MetricKey = (typeof METRICS)[number]['key']

function todayISO(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export default function SymptomDiaryPage() {
  const [diary, setDiary] = useState<SymptomDiary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')
  const [saving, setSaving] = useState(false)

  const [recordDate, setRecordDate] = useState(todayISO())
  const [scores, setScores] = useState<Record<MetricKey, number>>({
    cough: 0,
    dyspnea: 0,
    sputum: 0,
  })
  const [note, setNote] = useState('')

  const today = todayISO()

  async function load() {
    setLoading(true)
    try {
      setDiary(await api<SymptomDiary>('/api/symptoms?days=30'))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const existing = useMemo(
    () => diary?.items.find((x) => x.record_date === recordDate) ?? null,
    [diary, recordDate],
  )

  useEffect(() => {
    if (existing) {
      setScores({
        cough: existing.cough,
        dyspnea: existing.dyspnea,
        sputum: existing.sputum,
      })
      setNote(existing.note)
    } else {
      setScores({ cough: 0, dyspnea: 0, sputum: 0 })
      setNote('')
    }
  }, [existing])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setTip('')
    try {
      const saved = await api<SymptomEntry>('/api/symptoms', {
        method: 'POST',
        body: JSON.stringify({
          record_date: recordDate,
          cough: scores.cough,
          dyspnea: scores.dyspnea,
          sputum: scores.sputum,
          note: note.trim(),
        }),
      })
      setTip(
        saved.warning
          ? `已保存。${saved.warning_text}`
          : '已保存今天的症状记录',
      )
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function onDelete(entry: SymptomEntry) {
    if (!confirm(`删除 ${formatDate(entry.record_date)} 的记录？`)) return
    try {
      await api(`/api/symptoms/${entry.id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  return (
    <div className="screen stack-gap">
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <div>
          <h1>症状日记</h1>
          <p className="sub">每天记录咳嗽、气短与痰量，观察变化趋势</p>
        </div>
        <Link to="/vitals" className="linkish">
          健康监测 ›
        </Link>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {tip ? <p className="ok-tip">{tip}</p> : null}

      {diary?.warning ? (
        <div className="symptom-warning">
          <strong>近期症状有加重迹象</strong>
          <p>{diary.warning_text}</p>
        </div>
      ) : null}

      <form className="form-card" onSubmit={onSubmit}>
        <h2>{existing ? '更新记录' : '记录症状'}</h2>
        <label>
          日期
          <input
            type="date"
            value={recordDate}
            max={today}
            onChange={(e) => setRecordDate(e.target.value || today)}
            required
          />
        </label>
        {METRICS.map((m) => (
          <div key={m.key} className="symptom-scale">
            <span className="symptom-scale-label">{m.label}</span>
            <div className="chip-row">
              {[0, 1, 2, 3].map((level) => (
                <button
                  key={level}
                  type="button"
                  className={`chip${scores[m.key] === level ? ' active' : ''}`}
                  onClick={() => setScores((prev) => ({ ...prev, [m.key]: level }))}
                >
                  {level} · {SCALE_LABELS[level]}
                </button>
              ))}
            </div>
          </div>
        ))}
        <label>
          备注（可选）
          <textarea
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="如：夜间咳嗽加重、活动后气短等"
            maxLength={1000}
          />
        </label>
        <p className="meta" style={{ margin: 0 }}>
          当前合计 {scores.cough + scores.dyspnea + scores.sputum} / 9
          {existing ? ` · ${formatDate(existing.record_date)} 已有记录，提交将覆盖` : ''}
        </p>
        <button className="btn primary block" type="submit" disabled={saving}>
          {saving ? '保存中…' : existing ? '更新记录' : '保存记录'}
        </button>
      </form>

      <section>
        <h3 className="section-label">近 30 天记录</h3>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : !diary || diary.items.length === 0 ? (
          <p className="muted">还没有记录，从今天开始吧。</p>
        ) : (
          <ul className="list-card">
            {diary.items.map((item) => (
              <li key={item.id}>
                <h3>
                  {formatDate(item.record_date)}
                  <span className={`badge ${item.warning ? 'danger' : 'soft'}`}>
                    合计 {item.total}
                  </span>
                </h3>
                <p className="meta">
                  咳嗽 {item.cough} · 气短 {item.dyspnea} · 痰量 {item.sputum}
                </p>
                {item.note ? <p style={{ margin: '6px 0 0' }}>{item.note}</p> : null}
                {item.warning ? (
                  <p className="error" style={{ margin: '6px 0 0' }}>
                    {item.warning_text}
                  </p>
                ) : null}
                <p className="meta">更新于 {formatDateTime(item.updated_at)}</p>
                <div className="row-actions">
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => setRecordDate(item.record_date)}
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => void onDelete(item)}
                  >
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {diary?.disclaimer ? (
          <p className="mall-footnote">{diary.disclaimer}</p>
        ) : null}
      </section>
    </div>
  )
}
