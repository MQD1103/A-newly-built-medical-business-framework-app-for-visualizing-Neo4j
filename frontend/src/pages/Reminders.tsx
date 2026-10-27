import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, Reminder, ReminderKind, RepeatRule } from '../types'
import { formatDateTime } from '../utils'

const KIND_LABEL: Record<ReminderKind, string> = {
  general: '其他事项',
  medication: '用药',
  oxygen: '吸氧',
  rehab: '康复训练',
  vitals: '测血氧',
  checkup: '复查',
  assessment: '量表评估',
  vaccine: '疫苗接种',
}

const KIND_ICON: Record<ReminderKind, string> = {
  general: '📌',
  medication: '💊',
  oxygen: '🫧',
  rehab: '🚶',
  vitals: '🫁',
  checkup: '🏥',
  assessment: '📋',
  vaccine: '💉',
}

/** 各类型在卡片上展示的「明细」字段名（primary 存 drug_name 或 check_type） */
const KIND_DETAIL: Partial<Record<ReminderKind, { primary: string; secondary: string }>> = {
  medication: { primary: '用药', secondary: '用法' },
  oxygen: { primary: '设备', secondary: '流量与时长' },
  rehab: { primary: '训练项目', secondary: '频次时长' },
  vitals: { primary: '监测项目', secondary: '目标值' },
  checkup: { primary: '检查项目', secondary: '' },
  assessment: { primary: '量表', secondary: '频次' },
  vaccine: { primary: '疫苗', secondary: '剂次' },
}

/** 新建时用哪些字段：primary 写 drug_name（vitals/assessment 写 check_type） */
const KIND_FIELD: Record<
  ReminderKind,
  {
    title: string
    primary?: string
    primaryLabel?: string
    secondary?: string
    secondaryLabel?: string
    repeat?: RepeatRule
    useCheckType?: boolean
  }
> = {
  general: { title: '任何想提醒的事' },
  medication: {
    title: '如：早上吸入噻托溴铵',
    primary: '如：噻托溴铵吸入粉雾剂',
    primaryLabel: '药名',
    secondary: '如：1 吸，每日一次',
    secondaryLabel: '剂量 / 用法',
    repeat: 'daily',
  },
  oxygen: {
    title: '如：下午家庭氧疗',
    primary: '如：家用制氧机 / 便携液氧',
    primaryLabel: '设备',
    secondary: '如：2 L/min，每天累计 ≥15 小时',
    secondaryLabel: '流量与时长',
    repeat: 'daily',
  },
  rehab: {
    title: '如：呼吸操与步行训练',
    primary: '如：缩唇呼吸 + 腹式呼吸 + 步行',
    primaryLabel: '训练项目',
    secondary: '如：20 分钟 / 次，每周 5 次',
    secondaryLabel: '频次与时长',
    repeat: 'daily',
  },
  vitals: {
    title: '如：早晚测血氧并记录',
    primary: '如：血氧 SpO₂ + 心率',
    primaryLabel: '监测项目',
    secondary: '如：SpO₂ ≥ 92%，低于 88% 联系医生',
    secondaryLabel: '目标值 / 警戒线',
    repeat: 'daily',
    useCheckType: true,
  },
  checkup: {
    title: '如：呼吸科复查',
    primary: '如：肺功能、胸部 CT',
    primaryLabel: '检查项目',
    useCheckType: true,
  },
  assessment: {
    title: '如：重做 CAT 评分',
    primary: '如：CAT 生活质量评分 / mMRC',
    primaryLabel: '量表名称',
    secondary: '如：每月一次，复诊前一周',
    secondaryLabel: '评估频次',
    useCheckType: true,
  },
  vaccine: {
    title: '如：接种流感疫苗',
    primary: '如：流感疫苗 / 肺炎球菌疫苗',
    primaryLabel: '疫苗名称',
    secondary: '如：每年 1 剂（秋季）',
    secondaryLabel: '剂次',
  },
}

/** 空态一键模板：点一下把表单填好，时间默认明天 08:00 */
const TEMPLATES: { kind: ReminderKind; title: string; hour: number; primary: string; secondary: string }[] = [
  { kind: 'medication', title: '按时使用吸入药', hour: 8, primary: '噻托溴铵', secondary: '1 吸，每日一次' },
  { kind: 'oxygen', title: '家庭氧疗', hour: 14, primary: '家用制氧机', secondary: '2 L/min，每天累计 ≥15 小时' },
  { kind: 'rehab', title: '呼吸康复训练', hour: 16, primary: '缩唇呼吸 + 步行', secondary: '20 分钟，每周 5 次' },
  { kind: 'vitals', title: '测血氧并记录', hour: 20, primary: '血氧 SpO₂ + 心率', secondary: '目标 SpO₂ ≥ 92%' },
  { kind: 'checkup', title: '呼吸科复查', hour: 9, primary: '肺功能 + 胸部 CT', secondary: '' },
  { kind: 'assessment', title: '重做 CAT 评分', hour: 20, primary: 'CAT 生活质量评分', secondary: '每月一次' },
  { kind: 'vaccine', title: '接种流感疫苗', hour: 10, primary: '流感疫苗', secondary: '每年 1 剂' },
]

const FILTER_ORDER: (ReminderKind | 'all')[] = [
  'all',
  'medication',
  'oxygen',
  'rehab',
  'vitals',
  'checkup',
  'assessment',
  'vaccine',
]

/** 卡片上的明细行：按类型把 drug_name / check_type / dosage 拼成可读文案 */
function detailText(r: Reminder): string {
  const meta = KIND_DETAIL[r.kind]
  if (!meta) return ''
  const primary = r.drug_name || r.check_type
  const parts: string[] = []
  if (primary) parts.push(`${meta.primary}：${primary}`)
  if (r.dosage && meta.secondary) parts.push(`${meta.secondary}：${r.dosage}`)
  return parts.join(' · ')
}

const REPEAT_LABEL: Record<RepeatRule, string> = {
  none: '不重复',
  daily: '每天',
  weekly: '每周',
}

function toLocalInput(iso: string): string {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function Reminders() {
  const { user } = useAuth()
  const [items, setItems] = useState<Reminder[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [dueAt, setDueAt] = useState('')
  const [url, setUrl] = useState('')
  const [courseId, setCourseId] = useState('')
  const [kind, setKind] = useState<ReminderKind>('general')
  const [drugName, setDrugName] = useState('')
  const [dosage, setDosage] = useState('')
  const [repeatRule, setRepeatRule] = useState<RepeatRule>('none')
  const [checkType, setCheckType] = useState('')
  const [prepQuestions, setPrepQuestions] = useState('')
  const [kindFilter, setKindFilter] = useState<ReminderKind | 'all'>('all')

  const canPickCourse = user?.role === 'admin'

  async function load() {
    try {
      const reminders = await api<Reminder[]>('/api/reminders')
      setItems(reminders)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  async function loadCourses() {
    if (!canPickCourse) return
    try {
      const path = user?.role === 'admin' ? '/api/courses/all' : '/api/courses'
      setCourses(await api<Course[]>(path))
    } catch {
      setCourses([])
    }
  }

  useEffect(() => {
    void load()
    void loadCourses()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role])

  function resetForm() {
    setTitle('')
    setContent('')
    setDueAt('')
    setUrl('')
    setCourseId('')
    setKind('general')
    setDrugName('')
    setDosage('')
    setRepeatRule('none')
    setCheckType('')
    setPrepQuestions('')
    setEditId(null)
  }

  function openCreate() {
    resetForm()
    setShowForm(true)
  }

  /** 空态模板：把类型、标题、明细、重复规则一次填好，时间默认明天对应时段 */
  function startFromTemplate(t: (typeof TEMPLATES)[number]) {
    resetForm()
    const meta = KIND_FIELD[t.kind]
    const date = new Date()
    date.setDate(date.getDate() + 1)
    date.setHours(t.hour, 0, 0, 0)
    const pad = (n: number) => String(n).padStart(2, '0')
    setKind(t.kind)
    setTitle(t.title)
    setDueAt(
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
        date.getHours(),
      )}:00`,
    )
    if (meta.useCheckType) setCheckType(t.primary)
    else setDrugName(t.primary)
    setDosage(t.secondary)
    setRepeatRule(meta.repeat ?? 'none')
    setShowForm(true)
  }

  function openEdit(r: Reminder) {    setEditId(r.id)
    setTitle(r.title)
    setContent(r.content || '')
    setDueAt(toLocalInput(r.due_at))
    setUrl(r.external_url || '')
    setCourseId(r.course_id ? String(r.course_id) : '')
    setKind(r.kind || 'general')
    setDrugName(r.drug_name || '')
    setDosage(r.dosage || '')
    setRepeatRule(r.repeat_rule || 'none')
    setCheckType(r.check_type || '')
    setPrepQuestions(r.prep_questions || '')
    setShowForm(true)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const meta = KIND_FIELD[kind]
    const usePrimary = Boolean(meta.primary)
    const detail: Record<string, unknown> = {
      title: title.trim(),
      content: content.trim(),
      due_at: new Date(dueAt).toISOString(),
      external_url: url.trim(),
      kind,
      repeat_rule: repeatRule,
      // 设备 / 训练项目 / 疫苗名也复用 drug_name 存，避免为每种类型加字段
      drug_name: usePrimary && !meta.useCheckType ? drugName.trim() : '',
      dosage: usePrimary && meta.secondary ? dosage.trim() : '',
      check_type: usePrimary && meta.useCheckType ? checkType.trim() : '',
      prep_questions: kind === 'checkup' ? prepQuestions.trim() : '',
    }
    try {
      if (editId != null) {
        await api(`/api/reminders/${editId}`, {
          method: 'PATCH',
          body: JSON.stringify(detail),
        })
      } else {
        const body: Record<string, unknown> = { ...detail }
        if (canPickCourse && courseId) {
          body.course_id = Number(courseId)
        }
        await api('/api/reminders', {
          method: 'POST',
          body: JSON.stringify(body),
        })
      }
      resetForm()
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : editId ? '保存失败' : '创建失败')
    }
  }

  async function onDelete(id: number) {
    if (!confirm('确定删除？')) return
    try {
      await api(`/api/reminders/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  async function onToggleNotify(r: Reminder, enabled: boolean) {
    try {
      const updated = await api<Reminder>(`/api/reminders/${r.id}/notify`, {
        method: 'PUT',
        body: JSON.stringify({ enabled }),
      })
      setItems((prev) => prev.map((x) => (x.id === r.id ? updated : x)))
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败')
    }
  }

  async function onToggleComplete(r: Reminder) {
    try {
      await api<Reminder>(`/api/reminders/${r.id}/complete`, {
        method: 'POST',
        body: JSON.stringify({ completed: !r.completed }),
      })
      // 重复提醒完成后会生成下一周期，重新拉取才能看到
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败')
    }
  }

  function sourceLabel(source?: string) {
    if (source === 'system') return '系统'
    if (source === 'manager') return '管理'
    return '我的'
  }

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: items.length }
    for (const r of items) map[r.kind] = (map[r.kind] ?? 0) + 1
    return map
  }, [items])

  const visible = useMemo(
    () => (kindFilter === 'all' ? items : items.filter((r) => r.kind === kindFilter)),
    [items, kindFilter],
  )

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
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <div>
          <h1>提醒中心</h1>
          <p className="sub">用药 · 吸氧 · 康复 · 测血氧 · 复查 · 量表 · 疫苗</p>
        </div>
        <button
          type="button"
          className="btn-add"
          onClick={() => {
            if (showForm) {
              setShowForm(false)
              resetForm()
            } else {
              openCreate()
            }
          }}
          aria-label={showForm ? '取消' : '添加'}
          title={showForm ? '取消' : '添加'}
        >
          {showForm ? '×' : '+'}
        </button>
      </div>

      <div className="rem-kind-tabs">
        {FILTER_ORDER.map((k) => (
          <button
            key={k}
            type="button"
            className={`rem-kind-chip${kindFilter === k ? ' active' : ''}`}
            onClick={() => setKindFilter(k)}
          >
            <span>
              {k === 'all' ? '全部' : `${KIND_ICON[k]} ${KIND_LABEL[k]}`}
            </span>
            <span className="rem-kind-count">{counts[k] ?? 0}</span>
          </button>
        ))}
      </div>

      {showForm && (
        <form className="form-card" onSubmit={onSubmit}>
          <h2>{editId != null ? '编辑' : '添加'}</h2>
          <div className="rem-kind-pick">
            <span className="rem-kind-pick-label">类型</span>
            <div className="rem-kind-pick-grid">
              {(Object.keys(KIND_LABEL) as ReminderKind[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  className={`rem-kind-pick-item${kind === k ? ' active' : ''}`}
                  onClick={() => {
                    setKind(k)
                    const rule = KIND_FIELD[k].repeat
                    if (rule && repeatRule === 'none') setRepeatRule(rule)
                  }}
                >
                  <span aria-hidden="true">{KIND_ICON[k]}</span>
                  {KIND_LABEL[k]}
                </button>
              ))}
            </div>
          </div>
          <label>
            标题
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={KIND_FIELD[kind].title}
              required
            />
          </label>
          <label>
            截止时间
            <input
              type="datetime-local"
              value={dueAt}
              onChange={(e) => setDueAt(e.target.value)}
              required
            />
          </label>
          <label>
            重复
            <select
              value={repeatRule}
              onChange={(e) => setRepeatRule(e.target.value as RepeatRule)}
            >
              {(Object.keys(REPEAT_LABEL) as RepeatRule[]).map((rule) => (
                <option key={rule} value={rule}>
                  {REPEAT_LABEL[rule]}
                </option>
              ))}
            </select>
          </label>
          {repeatRule !== 'none' ? (
            <p className="meta" style={{ margin: 0 }}>
              完成后会自动生成下一{repeatRule === 'daily' ? '天' : '周'}的提醒，历史完成记录保留。
            </p>
          ) : null}
          {KIND_FIELD[kind].primary ? (
            <>
              <label>
                {KIND_FIELD[kind].primaryLabel}
                <input
                  value={KIND_FIELD[kind].useCheckType ? checkType : drugName}
                  onChange={(e) =>
                    KIND_FIELD[kind].useCheckType
                      ? setCheckType(e.target.value)
                      : setDrugName(e.target.value)
                  }
                  placeholder={KIND_FIELD[kind].primary}
                />
              </label>
              {KIND_FIELD[kind].secondary ? (
                <label>
                  {KIND_FIELD[kind].secondaryLabel}
                  <input
                    value={dosage}
                    onChange={(e) => setDosage(e.target.value)}
                    placeholder={KIND_FIELD[kind].secondary}
                  />
                </label>
              ) : null}
            </>
          ) : null}
          {kind === 'checkup' ? (
            <label>
              就诊前准备 / 想问医生的问题
              <textarea
                rows={3}
                value={prepQuestions}
                onChange={(e) => setPrepQuestions(e.target.value)}
                placeholder="如：是否需要空腹？最近气短加重，是否需要调药？"
              />
            </label>
          ) : null}
          {canPickCourse && editId == null && (
            <label>
              关联课程（可选）
              <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                <option value="">不关联 · 个人事项</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.semester ? ` · ${c.semester}` : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
          {canPickCourse && editId == null && courseId ? (
            <p className="meta">关联课程后将作为「管理」提醒发布，用户可见且不可删除</p>
          ) : null}
          {editId != null && courseId ? (
            <p className="meta">
              关联课程：{courses.find((c) => String(c.id) === courseId)?.name || '已关联'}
            </p>
          ) : null}
          <label>
            说明（可选）
            <textarea
              rows={3}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="补充说明，可留空"
            />
          </label>
          <label>
            链接（可选）
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
            />
          </label>
          <button className="btn primary block" type="submit">
            {editId != null ? '保存' : '创建'}
          </button>
        </form>
      )}

      <ul className="list-card">
        {visible.map((r) => {
          const locked = r.source === 'manager' || r.source === 'system'
          return (
            <li key={r.id}>
              <h3>
                {r.title}
                <span
                  className={`badge ${
                    r.completed ? 'ok' : r.status === 'overdue' ? 'danger' : 'soft'
                  }`}
                >
                  {r.completed ? '已完成' : r.status === 'overdue' ? '已过期' : '待完成'}
                </span>
                {r.kind !== 'general' ? (
                  <span className="badge soft">
                    {KIND_ICON[r.kind]} {KIND_LABEL[r.kind]}
                  </span>
                ) : null}
                <span className="badge soft">{sourceLabel(r.source)}</span>
              </h3>
              <p className="meta">
                {r.course_name ? `${r.course_name} · ` : ''}
                截止 {formatDateTime(r.due_at)}
                {r.repeat_rule !== 'none' ? ` · ${REPEAT_LABEL[r.repeat_rule]}重复` : ''}
                {r.completed_at ? ` · 完成于 ${formatDateTime(r.completed_at)}` : ''}
              </p>
              {detailText(r) ? <p className="meta">{detailText(r)}</p> : null}
              {r.content ? <p style={{ margin: '8px 0 0' }}>{r.content}</p> : null}
              {r.kind === 'checkup' && r.prep_questions ? (
                <div className="prep-box">
                  <strong>就诊前准备</strong>
                  <p style={{ whiteSpace: 'pre-wrap' }}>{r.prep_questions}</p>
                </div>
              ) : null}
              {r.external_url && (
                <a className="ext-link" href={r.external_url} target="_blank" rel="noreferrer">
                  打开链接 →
                </a>
              )}
              <div className="row-actions rem-actions">
                <button
                  type="button"
                  className={`linkish${r.completed ? '' : ' primary'}`}
                  onClick={() => void onToggleComplete(r)}
                >
                  {r.completed ? '取消完成' : '标记完成'}
                </button>
                {locked && (
                  <label className="rem-notify-toggle">
                    <input
                      type="checkbox"
                      checked={r.notify_enabled !== false}
                      onChange={(e) => void onToggleNotify(r, e.target.checked)}
                    />
                    <span>是否提醒</span>
                  </label>
                )}
                {r.can_edit && (
                  <button type="button" className="linkish" onClick={() => openEdit(r)}>
                    编辑
                  </button>
                )}
                {r.can_delete && (
                  <button type="button" className="linkish" onClick={() => void onDelete(r.id)}>
                    删除
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      {items.length === 0 ? (
        <section className="item-card rem-templates">
          <div className="tk-head">
            <h2>还没有提醒，先建一条</h2>
            <span className="tk-badge">点一下自动填好</span>
          </div>
          <p className="muted tk-intro">
            选一个常用场景，时间默认明天上午，创建前仍可修改。
          </p>
          <div className="rem-template-grid">
            {TEMPLATES.map((t) => (
              <button
                key={t.kind}
                type="button"
                className="rem-template"
                onClick={() => startFromTemplate(t)}
              >
                <span className="rem-template-icon" aria-hidden="true">
                  {KIND_ICON[t.kind]}
                </span>
                <strong>{KIND_LABEL[t.kind]}</strong>
                <span className="rem-template-title">{t.title}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}
      {items.length > 0 && visible.length === 0 ? (
        <p className="muted">该分类下暂无提醒，切到「全部」看看。</p>
      ) : null}
    </div>
  )
}
