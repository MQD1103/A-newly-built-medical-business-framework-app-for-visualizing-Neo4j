import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type {
  HospitalAuthorization,
  HospitalCaregiver,
  HospitalCaregivers,
  HospitalPartner,
  HospitalRecord,
  HospitalRecordType,
} from '../types'
import { formatDateTime } from '../utils'

const RECORD_TYPES: { value: HospitalRecordType | ''; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'advice', label: '医生嘱托' },
  { value: 'condition', label: '病情资料' },
  { value: 'record', label: '就诊记录' },
]

const RECORD_LABEL: Record<string, string> = {
  advice: '医生嘱托',
  condition: '病情资料',
  record: '就诊记录',
}

function defaultDueAt(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function Hospital() {
  const [partners, setPartners] = useState<HospitalPartner[]>([])
  const [auths, setAuths] = useState<HospitalAuthorization[]>([])
  const [records, setRecords] = useState<HospitalRecord[]>([])
  const [caregivers, setCaregivers] = useState<HospitalCaregivers>({
    granted: [],
    received: [],
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')
  const [busy, setBusy] = useState('')

  const [filter, setFilter] = useState<HospitalRecordType | ''>('')
  const [expanded, setExpanded] = useState<number | null>(null)

  // 授权表单
  const [authPartnerId, setAuthPartnerId] = useState('')
  const [patientRef, setPatientRef] = useState('')
  const [consent, setConsent] = useState(false)

  // 医生嘱托 → 提醒
  const [reminderRecord, setReminderRecord] = useState<number | null>(null)
  const [reminderTitle, setReminderTitle] = useState('')
  const [reminderDue, setReminderDue] = useState(defaultDueAt())

  // 照护者授权
  const [caregiverName, setCaregiverName] = useState('')
  const [relation, setRelation] = useState('家属')

  // 作为照护者查看他人资料
  const [viewing, setViewing] = useState<{ id: number; name: string } | null>(null)

  const patientQuery = viewing ? `?patient_id=${viewing.id}` : ''

  async function load() {
    setLoading(true)
    try {
      const [partnerList, authList, recordList, caregiverList] = await Promise.all([
        api<HospitalPartner[]>('/api/hospital/partners'),
        api<HospitalAuthorization[]>(`/api/hospital/authorizations${patientQuery}`),
        api<HospitalRecord[]>(`/api/hospital/records${patientQuery}`),
        api<HospitalCaregivers>('/api/hospital/caregivers'),
      ])
      setPartners(partnerList)
      setAuths(authList)
      setRecords(recordList)
      setCaregivers(caregiverList)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewing?.id])

  const activePartnerIds = useMemo(
    () => new Set(auths.filter((a) => a.status === 'active').map((a) => a.partner_id)),
    [auths],
  )

  const visibleRecords = useMemo(
    () => (filter ? records.filter((r) => r.record_type === filter) : records),
    [records, filter],
  )

  async function onAuthorize() {
    const partnerId = Number(authPartnerId)
    if (!partnerId) {
      setError('请选择合作医院')
      return
    }
    if (patientRef.trim().length < 4) {
      setError('请填写医院患者标识（至少 4 位）')
      return
    }
    if (!consent) {
      setError('请先勾选授权确认')
      return
    }
    setBusy('auth')
    setError('')
    setTip('')
    try {
      await api('/api/hospital/authorizations', {
        method: 'POST',
        body: JSON.stringify({
          partner_id: partnerId,
          patient_ref: patientRef.trim(),
          consent: true,
        }),
      })
      setAuthPartnerId('')
      setPatientRef('')
      setConsent(false)
      setTip('授权成功，可同步医院资料')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '授权失败')
    } finally {
      setBusy('')
    }
  }

  async function onSync(authId: number) {
    setBusy(`sync-${authId}`)
    setError('')
    setTip('')
    try {
      const res = await api<{ added: number; updated: number; total: number }>(
        `/api/hospital/authorizations/${authId}/sync`,
        { method: 'POST' },
      )
      setTip(`同步完成：新增 ${res.added} 条，更新 ${res.updated} 条，共 ${res.total} 条`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '同步失败')
    } finally {
      setBusy('')
    }
  }

  async function onRevoke(auth: HospitalAuthorization) {
    if (!confirm(`确定撤销「${auth.partner_name}」的资料授权？撤销后将无法查看该院资料。`)) {
      return
    }
    setBusy(`revoke-${auth.id}`)
    try {
      await api(`/api/hospital/authorizations/${auth.id}`, { method: 'DELETE' })
      setTip('已撤销授权')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '撤销失败')
    } finally {
      setBusy('')
    }
  }

  async function onCreateReminder(record: HospitalRecord) {
    setBusy(`reminder-${record.id}`)
    setError('')
    try {
      await api(`/api/hospital/records/${record.id}/reminder`, {
        method: 'POST',
        body: JSON.stringify({
          due_at: new Date(reminderDue).toISOString(),
          title: reminderTitle.trim() || record.title,
        }),
      })
      setTip('已根据医生嘱托创建提醒，可在「服务 → 提醒」中查看')
      setReminderRecord(null)
      setReminderTitle('')
      setReminderDue(defaultDueAt())
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建提醒失败')
    } finally {
      setBusy('')
    }
  }

  async function onGrantCaregiver() {
    const username = caregiverName.trim()
    if (!username) return
    setBusy('caregiver')
    setError('')
    try {
      await api('/api/hospital/caregivers', {
        method: 'POST',
        body: JSON.stringify({ caregiver_username: username, relation: relation.trim() || '照护者' }),
      })
      setCaregiverName('')
      setTip('已授权该家属查看你的医院资料（只读）')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '授权失败')
    } finally {
      setBusy('')
    }
  }

  async function onRevokeCaregiver(grant: HospitalCaregiver) {
    if (!confirm(`确定撤销对「${grant.caregiver_name || grant.patient_name}」的授权？`)) return
    setBusy(`cg-${grant.id}`)
    try {
      await api(`/api/hospital/caregivers/${grant.id}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '撤销失败')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="screen stack-gap">
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <div>
          <h1>医院资料</h1>
          <p className="sub">经你授权后，只读查看医院同步的病情资料与医生嘱托</p>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {tip ? <p className="ok-tip">{tip}</p> : null}

      <p className="notice-strip">
        医院资料全程只读，本应用不会修改病历、开药或调整医嘱；原始影像与医院凭据不会下发到前端。
      </p>

      {viewing ? (
        <div className="viewing-bar">
          <span>正在查看「{viewing.name}」的资料</span>
          <button
            type="button"
            className="linkish"
            onClick={() => setViewing(null)}
          >
            返回我的资料
          </button>
        </div>
      ) : null}

      <section>
        <h3 className="section-label">合作医院与授权</h3>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : partners.length === 0 ? (
          <p className="muted">暂无已开通的合作医院</p>
        ) : (
          <ul className="list-card">
            {partners.map((p) => {
              const auth = auths.find(
                (a) => a.partner_id === p.id && a.status === 'active',
              )
              return (
                <li key={p.id}>
                  <h3>
                    {p.name}
                    <span className={`badge ${auth ? 'ok' : 'soft'}`}>
                      {auth ? '已授权' : '未授权'}
                    </span>
                  </h3>
                  <p className="meta">
                    {[p.department, p.contact].filter(Boolean).join(' · ') || p.code}
                  </p>
                  {p.note ? <p className="meta">{p.note}</p> : null}
                  {auth ? (
                    <>
                      <p className="meta">
                        患者标识 {auth.patient_ref_masked} · 授权于{' '}
                        {formatDateTime(auth.authorized_at)}
                      </p>
                      <div className="row-actions">
                        {!viewing ? (
                          <>
                            <button
                              type="button"
                              className="linkish primary"
                              disabled={busy === `sync-${auth.id}`}
                              onClick={() => void onSync(auth.id)}
                            >
                              {busy === `sync-${auth.id}` ? '同步中…' : '同步资料'}
                            </button>
                            <button
                              type="button"
                              className="linkish"
                              disabled={busy === `revoke-${auth.id}`}
                              onClick={() => void onRevoke(auth)}
                            >
                              撤销授权
                            </button>
                          </>
                        ) : null}
                      </div>
                    </>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {!viewing ? (
        <section>
          <h3 className="section-label">新增 / 更新授权</h3>
          <div className="form-card">
            <p className="meta" style={{ marginTop: 0 }}>
              授权后仅同步医生嘱托、病情资料和就诊记录；可随时撤销。
            </p>
            <label>
              合作医院
              <select
                value={authPartnerId}
                onChange={(e) => setAuthPartnerId(e.target.value)}
              >
                <option value="">请选择</option>
                {partners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.department ? ` · ${p.department}` : ''}
                  </option>
                ))}
              </select>
            </label>
            <label>
              医院患者标识
              <input
                value={patientRef}
                onChange={(e) => setPatientRef(e.target.value)}
                placeholder="如就诊卡号 / 住院号"
              />
            </label>
            <label className="consent-row">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              <span>我确认授权本应用只读获取上述资料，用于自我管理与提醒</span>
            </label>
            <button
              type="button"
              className="btn primary block"
              disabled={busy === 'auth'}
              onClick={() => void onAuthorize()}
            >
              {busy === 'auth' ? '提交中…' : '确认授权'}
            </button>
          </div>
        </section>
      ) : null}

      <section>
        <h3 className="section-label">医院资料（只读）</h3>
        <div className="chip-row">
          {RECORD_TYPES.map((t) => (
            <button
              key={t.value || 'all'}
              type="button"
              className={`chip${filter === t.value ? ' active' : ''}`}
              onClick={() => setFilter(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : visibleRecords.length === 0 ? (
          <p className="muted">
            暂无资料。{activePartnerIds.size === 0 ? '请先完成医院授权。' : '可点击「同步资料」获取。'}
          </p>
        ) : (
          <ul className="list-card">
            {visibleRecords.map((r) => {
              const open = expanded === r.id
              const isAdvice = r.record_type === 'advice'
              return (
                <li key={r.id}>
                  <button
                    type="button"
                    className="record-head"
                    onClick={() => setExpanded(open ? null : r.id)}
                  >
                    <span>
                      <strong>{r.title}</strong>
                      <span className="meta">
                        {RECORD_LABEL[r.record_type] ?? r.record_type} · {r.partner_name}
                        {r.occurred_at ? ` · ${formatDateTime(r.occurred_at)}` : ''}
                      </span>
                    </span>
                    <span className="chev">{open ? '⌃' : '›'}</span>
                  </button>
                  {open ? (
                    <div className="record-body">
                      {r.doctor_name || r.department ? (
                        <p className="meta">
                          {[r.department, r.doctor_name].filter(Boolean).join(' · ')}
                        </p>
                      ) : null}
                      <p style={{ whiteSpace: 'pre-wrap', margin: '6px 0 0' }}>
                        {r.content || '（暂无内容）'}
                      </p>
                      <p className="meta">
                        同步于 {formatDateTime(r.fetched_at)} · 只读
                      </p>
                      {isAdvice && !viewing ? (
                        reminderRecord === r.id ? (
                          <div className="reminder-inline">
                            <label>
                              提醒标题（可选）
                              <input
                                value={reminderTitle}
                                onChange={(e) => setReminderTitle(e.target.value)}
                                placeholder={r.title}
                              />
                            </label>
                            <label>
                              提醒时间
                              <input
                                type="datetime-local"
                                value={reminderDue}
                                onChange={(e) => setReminderDue(e.target.value)}
                              />
                            </label>
                            <div className="row-actions">
                              <button
                                type="button"
                                className="btn primary small"
                                disabled={busy === `reminder-${r.id}`}
                                onClick={() => void onCreateReminder(r)}
                              >
                                {busy === `reminder-${r.id}` ? '创建中…' : '创建提醒'}
                              </button>
                              <button
                                type="button"
                                className="linkish"
                                onClick={() => setReminderRecord(null)}
                              >
                                取消
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="row-actions">
                            <button
                              type="button"
                              className="linkish primary"
                              onClick={() => {
                                setReminderRecord(r.id)
                                setReminderTitle('')
                                setReminderDue(defaultDueAt())
                              }}
                            >
                              设为提醒
                            </button>
                          </div>
                        )
                      ) : null}
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section>
        <h3 className="section-label">照护者授权</h3>
        <div className="form-card">
          <p className="meta" style={{ marginTop: 0 }}>
            授权家属只读查看你的医院资料，便于日常照护。
          </p>
          <div className="row-actions" style={{ alignItems: 'center' }}>
            <input
              value={caregiverName}
              onChange={(e) => setCaregiverName(e.target.value)}
              placeholder="家属用户名"
              aria-label="家属用户名"
              style={{ flex: 1 }}
            />
            <input
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
              placeholder="关系"
              aria-label="关系"
              style={{ width: 80 }}
            />
            <button
              type="button"
              className="btn small"
              disabled={busy === 'caregiver' || !caregiverName.trim()}
              onClick={() => void onGrantCaregiver()}
            >
              授权
            </button>
          </div>
        </div>

        {caregivers.granted.length > 0 ? (
          <ul className="list-card" style={{ marginTop: 10 }}>
            {caregivers.granted.map((g) => (
              <li key={g.id}>
                <h3>
                  {g.caregiver_name || '照护者'}
                  <span className={`badge ${g.status === 'active' ? 'ok' : 'soft'}`}>
                    {g.status === 'active' ? '生效中' : '已撤销'}
                  </span>
                </h3>
                <p className="meta">
                  {g.relation} · 授权于 {formatDateTime(g.granted_at)}
                </p>
                {g.status === 'active' ? (
                  <div className="row-actions">
                    <button
                      type="button"
                      className="linkish"
                      disabled={busy === `cg-${g.id}`}
                      onClick={() => void onRevokeCaregiver(g)}
                    >
                      撤销
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}

        {caregivers.received.length > 0 ? (
          <>
            <p className="meta" style={{ marginTop: 14 }}>
              我可查看的患者资料
            </p>
            <ul className="list-card">
              {caregivers.received.map((g) => (
                <li key={g.id}>
                  <h3>
                    {g.patient_name || '患者'}
                    <span className="badge soft">{g.relation}</span>
                  </h3>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="linkish primary"
                      onClick={() =>
                        setViewing({
                          id: g.patient_user_id,
                          name: g.patient_name || '患者',
                        })
                      }
                    >
                      查看资料
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>
    </div>
  )
}
