import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { HealthProfile, HealthProfileOut } from '../types'
import { formatDateTime } from '../utils'

const EMPTY: HealthProfile = {
  sex: '',
  birth_year: '',
  height_cm: '',
  weight_kg: '',
  blood_type: '',
  diagnosis: '',
  diagnosed_at: '',
  copd_grade: '',
  fev1_percent: '',
  fev1_fvc: '',
  oxygen_target: '',
  current_meds: '',
  allergies: '',
  past_history: '',
  emergency_name: '',
  emergency_relation: '',
  emergency_phone: '',
  doctor_name: '',
  doctor_hospital: '',
  doctor_dept: '',
  doctor_phone: '',
  notes: '',
}

const GRADES = [
  { value: '', label: '未评估 / 不清楚' },
  { value: 'GOLD 1', label: 'GOLD 1 · 轻度（FEV1 ≥ 80%）' },
  { value: 'GOLD 2', label: 'GOLD 2 · 中度（FEV1 50–79%）' },
  { value: 'GOLD 3', label: 'GOLD 3 · 重度（FEV1 30–49%）' },
  { value: 'GOLD 4', label: 'GOLD 4 · 极重度（FEV1 < 30%）' },
]

const BLOOD_TYPES = ['', 'A', 'B', 'O', 'AB', '不详']

type FieldKey = keyof HealthProfile

/** 与后端 CHECK_FIELDS 保持一致：输入过程中即时算完整度，保存后仍以后端返回值校准 */
const CHECK_FIELDS: { key: FieldKey; label: string }[] = [
  { key: 'sex', label: '性别' },
  { key: 'birth_year', label: '出生年份' },
  { key: 'height_cm', label: '身高' },
  { key: 'weight_kg', label: '体重' },
  { key: 'diagnosis', label: '诊断' },
  { key: 'copd_grade', label: '肺功能分级' },
  { key: 'fev1_percent', label: 'FEV1 占预计值' },
  { key: 'current_meds', label: '当前用药' },
  { key: 'allergies', label: '过敏史' },
  { key: 'past_history', label: '既往病史' },
  { key: 'emergency_name', label: '紧急联系人' },
  { key: 'emergency_phone', label: '紧急联系人电话' },
  { key: 'doctor_name', label: '主治医生' },
  { key: 'doctor_hospital', label: '就诊医院' },
]

export default function HealthProfilePage() {
  const [form, setForm] = useState<HealthProfile>(EMPTY)
  const [meta, setMeta] = useState<{ completeness: number; missing: string[]; updated_at: string | null }>({
    completeness: 0,
    missing: [],
    updated_at: null,
  })
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')

  useEffect(() => {
    let alive = true
    async function load() {
      try {
        const data = await api<HealthProfileOut>('/api/health-profile')
        if (!alive) return
        setForm({ ...EMPTY, ...pickProfile(data) })
        setName(data.full_name)
        setMeta({
          completeness: data.completeness,
          missing: data.missing,
          updated_at: data.updated_at,
        })
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : '加载失败')
      } finally {
        if (alive) setLoading(false)
      }
    }
    void load()
    return () => {
      alive = false
    }
  }, [])

  function set<K extends FieldKey>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function save() {
    setSaving(true)
    setError('')
    setTip('')
    try {
      const data = await api<HealthProfileOut>('/api/health-profile', {
        method: 'PUT',
        body: JSON.stringify(form),
      })
      setMeta({
        completeness: data.completeness,
        missing: data.missing,
        updated_at: data.updated_at,
      })
      setTip(`已保存 · 档案完整度 ${data.completeness}%`)
      window.setTimeout(() => setTip(''), 2600)
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // 由身高体重算 BMI，仅作提示，不写库
  const bmi = (() => {
    const h = Number(form.height_cm)
    const w = Number(form.weight_kg)
    if (!h || !w) return null
    return Number((w / (h / 100) ** 2).toFixed(1))
  })()

  const bmiHint =
    bmi === null
      ? ''
      : bmi < 18.5
        ? '偏低，慢阻肺患者需警惕营养不良'
        : bmi < 24
          ? '正常范围'
          : bmi < 28
            ? '偏高'
            : '明显偏高'

  // 输入即算：改动字段时完整度立刻跟着动，不用等保存
  const live = (() => {
    const missing = CHECK_FIELDS.filter((f) => !(form[f.key] || '').trim()).map((f) => f.label)
    return {
      pct: Math.round(((CHECK_FIELDS.length - missing.length) * 100) / CHECK_FIELDS.length),
      missing,
    }
  })()

  if (loading) {
    return (
      <div className="screen stack-gap">
        <p className="muted">加载中…</p>
      </div>
    )
  }

  return (
    <div className="screen stack-gap health-profile">
      <div className="page-title no-print">
        <div>
          <h1>个人健康档案</h1>
          <p className="sub">就诊时可直接出示，避免临时回忆</p>
        </div>
        <Link to="/me" className="linkish">
          返回我的
        </Link>
      </div>

      <section className="hp-summary">
        <div className="hp-summary-top">
          <div>
            <strong>{name || '我的档案'}</strong>
            <span className="hp-summary-sub">
              {form.diagnosis || '尚未填写诊断'}
              {form.copd_grade ? ` · ${form.copd_grade}` : ''}
            </span>
          </div>
          <span className="hp-pct">{live.pct}%</span>
        </div>
        <div className="hp-bar">
          <span style={{ width: `${live.pct}%` }} />
        </div>
        <p className="hp-summary-hint">
          {live.missing.length === 0
            ? '档案已填写完整，建议每半年核对一次用药与分级。'
            : `还差 ${live.missing.length} 项：${live.missing.slice(0, 5).join('、')}${
                live.missing.length > 5 ? ' 等' : ''
              }`}
        </p>
        {meta.updated_at ? (
          <p className="meta hp-updated">最近更新：{formatDateTime(meta.updated_at)}</p>
        ) : null}
      </section>

      {error ? <p className="error">{error}</p> : null}
      {tip ? <p className="ok-tip no-print">{tip}</p> : null}

      <section className="item-card">
        <div className="tk-head">
          <h2>个人信息</h2>
          <span className="tk-badge">基础资料</span>
        </div>
        <div className="hp-grid">
          <div className="hp-field">
            <span>性别</span>
            <div className="vitals-seg">
              {['男', '女'].map((s) => (
                <button
                  key={s}
                  type="button"
                  className={form.sex === s ? 'active' : ''}
                  onClick={() => set('sex', form.sex === s ? '' : s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <label className="hp-field">
            <span>出生年份</span>
            <input
              inputMode="numeric"
              placeholder="1958"
              value={form.birth_year}
              onChange={(e) => set('birth_year', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>身高 (cm)</span>
            <input
              inputMode="decimal"
              placeholder="170"
              value={form.height_cm}
              onChange={(e) => set('height_cm', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>体重 (kg)</span>
            <input
              inputMode="decimal"
              placeholder="58"
              value={form.weight_kg}
              onChange={(e) => set('weight_kg', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>血型</span>
            <select value={form.blood_type} onChange={(e) => set('blood_type', e.target.value)}>
              {BLOOD_TYPES.map((b) => (
                <option key={b || 'none'} value={b}>
                  {b || '未填'}
                </option>
              ))}
            </select>
          </label>
          {bmi !== null ? (
            <div className="hp-field hp-bmi">
              <span>BMI（自动计算）</span>
              <p>
                {bmi} <span className="meta">· {bmiHint}</span>
              </p>
            </div>
          ) : null}
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>诊断与肺功能</h2>
          <span className="tk-badge">按出院小结填</span>
        </div>
        <div className="hp-grid">
          <label className="hp-field wide">
            <span>诊断</span>
            <input
              placeholder="如：慢性阻塞性肺疾病（COPD）"
              value={form.diagnosis}
              onChange={(e) => set('diagnosis', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>确诊时间</span>
            <input
              type="date"
              value={form.diagnosed_at}
              onChange={(e) => set('diagnosed_at', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>FEV1 占预计值 (%)</span>
            <input
              inputMode="decimal"
              placeholder="58"
              value={form.fev1_percent}
              onChange={(e) => set('fev1_percent', e.target.value)}
            />
          </label>
          <label className="hp-field wide">
            <span>肺功能分级（GOLD）</span>
            <select value={form.copd_grade} onChange={(e) => set('copd_grade', e.target.value)}>
              {GRADES.map((g) => (
                <option key={g.value || 'none'} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </label>
          <label className="hp-field">
            <span>FEV1/FVC (%)</span>
            <input
              inputMode="decimal"
              placeholder="52"
              value={form.fev1_fvc}
              onChange={(e) => set('fev1_fvc', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>氧疗目标 SpO₂</span>
            <input
              placeholder="88–92%"
              value={form.oxygen_target}
              onChange={(e) => set('oxygen_target', e.target.value)}
            />
          </label>
        </div>
        <p className="meta tk-note">
          GOLD 分级由 FEV1 占预计值决定，需以肺功能报告与医生判断为准；不确定就选「未评估」，不要自行推断。
        </p>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>当前用药</h2>
          <span className="tk-badge">每行一种</span>
        </div>
        <p className="muted tk-intro">
          写法建议：药名 + 装置 + 剂量 + 时间。例如「噻托溴铵 · 都保 · 1 吸 · 每晚」。
        </p>
        <textarea
          className="hp-textarea"
          rows={5}
          placeholder={'噻托溴铵 · 都保 · 1 吸 · 每晚\n沙丁胺醇 · 气雾剂+储雾罐 · 2 揿 · 按需'}
          value={form.current_meds}
          onChange={(e) => set('current_meds', e.target.value)}
        />
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>过敏史与既往病史</h2>
          <span className="tk-badge">就诊必问</span>
        </div>
        <div className="hp-stack">
          <label className="hp-field wide">
            <span>过敏史（药物 / 食物 / 其他）</span>
            <textarea
              className="hp-textarea"
              rows={3}
              placeholder="如：青霉素过敏（皮疹）；无其他"
              value={form.allergies}
              onChange={(e) => set('allergies', e.target.value)}
            />
          </label>
          <label className="hp-field wide">
            <span>既往病史</span>
            <textarea
              className="hp-textarea"
              rows={3}
              placeholder="如：高血压 10 年、2 型糖尿病；2023 年因急性加重住院 1 次"
              value={form.past_history}
              onChange={(e) => set('past_history', e.target.value)}
            />
          </label>
          <label className="hp-field wide">
            <span>其他备注</span>
            <textarea
              className="hp-textarea"
              rows={2}
              placeholder="如：行动不便、需要轮椅；听力下降"
              value={form.notes}
              onChange={(e) => set('notes', e.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>紧急联系人</h2>
          <span className="tk-badge">急救时用</span>
        </div>
        <div className="hp-grid">
          <label className="hp-field">
            <span>姓名</span>
            <input
              placeholder="如：张小明"
              value={form.emergency_name}
              onChange={(e) => set('emergency_name', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>与本人关系</span>
            <input
              placeholder="如：儿子"
              value={form.emergency_relation}
              onChange={(e) => set('emergency_relation', e.target.value)}
            />
          </label>
          <label className="hp-field wide">
            <span>联系电话</span>
            <input
              inputMode="tel"
              placeholder="138 0000 0000"
              value={form.emergency_phone}
              onChange={(e) => set('emergency_phone', e.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>主治医生</h2>
          <span className="tk-badge">复诊联系</span>
        </div>
        <div className="hp-grid">
          <label className="hp-field">
            <span>医生姓名</span>
            <input
              placeholder="如：李医生"
              value={form.doctor_name}
              onChange={(e) => set('doctor_name', e.target.value)}
            />
          </label>
          <label className="hp-field">
            <span>科室</span>
            <input
              placeholder="呼吸内科"
              value={form.doctor_dept}
              onChange={(e) => set('doctor_dept', e.target.value)}
            />
          </label>
          <label className="hp-field wide">
            <span>就诊医院</span>
            <input
              placeholder="如：市第一人民医院"
              value={form.doctor_hospital}
              onChange={(e) => set('doctor_hospital', e.target.value)}
            />
          </label>
          <label className="hp-field wide">
            <span>联系电话 / 预约方式</span>
            <input
              placeholder="如：门诊电话 0xxx-xxxxxxx"
              value={form.doctor_phone}
              onChange={(e) => set('doctor_phone', e.target.value)}
            />
          </label>
        </div>
      </section>

      <div className="hp-actions no-print">
        <button type="button" className="btn primary block" disabled={saving} onClick={() => void save()}>
          {saving ? '保存中…' : '保存档案'}
        </button>
        <button type="button" className="btn small block" onClick={() => window.print()}>
          打印 / 存为 PDF
        </button>
      </div>

      <p className="meta tk-foot no-print">
        档案保存在本系统的数据库中，仅你本人与管理员可见，用于就诊时快速出示与自我管理。
        内容以出院小结、肺功能报告和处方为准，不确定的项可以留空。
      </p>
    </div>
  )
}

/** 只取 HealthProfile 里的字段，忽略 id / completeness 等附加字段 */
function pickProfile(data: HealthProfileOut): HealthProfile {
  const out: HealthProfile = { ...EMPTY }
  for (const key of Object.keys(EMPTY) as FieldKey[]) {
    const value = data[key]
    out[key] = typeof value === 'string' ? value : ''
  }
  return out
}
