import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course } from '../types'
import { formatDateTime, roleLabel } from '../utils'

type Tab = 'family' | 'hospital' | 'course'

interface PurchaseRow {
  id: number
  course_id: number
  course_name: string
  amount: number
  status: string
  created_at: string
}

interface FamilyItem {
  id: number
  name: string
  relation: string
  phone: string
  note: string
  created_at: string
}

interface HospitalItem {
  id: number
  hospital_name: string
  department: string
  doctor_name: string
  phone: string
  address: string
  note: string
  created_at: string
}

const RELATIONS = ['配偶', '子女', '父母', '兄弟姐妹', '其他家人']

export default function LinkedInfo() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('family')
  const [error, setError] = useState('')

  const [family, setFamily] = useState<FamilyItem[]>([])
  const [hospitals, setHospitals] = useState<HospitalItem[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [purchases, setPurchases] = useState<PurchaseRow[]>([])

  const [showFamilyForm, setShowFamilyForm] = useState(false)
  const [fName, setFName] = useState('')
  const [fRelation, setFRelation] = useState('配偶')
  const [fPhone, setFPhone] = useState('')
  const [fNote, setFNote] = useState('')

  const [showHospitalForm, setShowHospitalForm] = useState(false)
  const [hName, setHName] = useState('')
  const [hDept, setHDept] = useState('')
  const [hDoctor, setHDoctor] = useState('')
  const [hPhone, setHPhone] = useState('')
  const [hAddr, setHAddr] = useState('')
  const [hNote, setHNote] = useState('')

  async function loadAll() {
    const [c, p, f, h] = await Promise.all([
      api<Course[]>('/api/courses'),
      api<PurchaseRow[]>('/api/courses/purchases/mine').catch(() => []),
      api<FamilyItem[]>('/api/links/family'),
      api<HospitalItem[]>('/api/links/hospitals'),
    ])
    setCourses(c.filter((x) => x.enrolled))
    setPurchases(p)
    setFamily(f)
    setHospitals(h)
  }

  useEffect(() => {
    void loadAll().catch((e: Error) => setError(e.message || '加载失败'))
  }, [])

  async function onAddFamily(e: FormEvent) {
    e.preventDefault()
    try {
      await api('/api/links/family', {
        method: 'POST',
        body: JSON.stringify({
          name: fName.trim(),
          relation: fRelation,
          phone: fPhone.trim(),
          note: fNote.trim(),
        }),
      })
      setFName('')
      setFPhone('')
      setFNote('')
      setShowFamilyForm(false)
      setFamily(await api<FamilyItem[]>('/api/links/family'))
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败')
    }
  }

  async function onDelFamily(id: number) {
    if (!confirm('删除该家人关联？')) return
    await api(`/api/links/family/${id}`, { method: 'DELETE' })
    setFamily((prev) => prev.filter((x) => x.id !== id))
  }

  async function onAddHospital(e: FormEvent) {
    e.preventDefault()
    try {
      await api('/api/links/hospitals', {
        method: 'POST',
        body: JSON.stringify({
          hospital_name: hName.trim(),
          department: hDept.trim(),
          doctor_name: hDoctor.trim(),
          phone: hPhone.trim(),
          address: hAddr.trim(),
          note: hNote.trim(),
        }),
      })
      setHName('')
      setHDept('')
      setHDoctor('')
      setHPhone('')
      setHAddr('')
      setHNote('')
      setShowHospitalForm(false)
      setHospitals(await api<HospitalItem[]>('/api/links/hospitals'))
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败')
    }
  }

  async function onDelHospital(id: number) {
    if (!confirm('删除该医院关联？')) return
    await api(`/api/links/hospitals/${id}`, { method: 'DELETE' })
    setHospitals((prev) => prev.filter((x) => x.id !== id))
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
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <div>
          <h1>关联信息</h1>
          <p className="sub">家人 · 医院 · 课程</p>
        </div>
      </div>

      <section className="item-card">
        <h3>账号</h3>
        <p className="meta" style={{ marginTop: 8 }}>
          {user?.full_name} · {user?.username} · {roleLabel(user?.role ?? '')}
        </p>
      </section>

      <div className="link-tabs">
        {(
          [
            ['family', '家人'],
            ['hospital', '医院'],
            ['course', '课程'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`link-tab${tab === key ? ' active' : ''}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'family' && (
        <>
          <div className="page-title" style={{ marginTop: 0 }}>
            <h2 style={{ fontSize: '1.05rem', margin: 0 }}>家人关联</h2>
            <button
              type="button"
              className="btn-add"
              onClick={() => setShowFamilyForm((v) => !v)}
              aria-label={showFamilyForm ? '取消' : '添加家人'}
            >
              {showFamilyForm ? '×' : '+'}
            </button>
          </div>
          {showFamilyForm && (
            <form className="form-card" onSubmit={onAddFamily}>
              <label>
                姓名
                <input value={fName} onChange={(e) => setFName(e.target.value)} required />
              </label>
              <label>
                关系
                <select value={fRelation} onChange={(e) => setFRelation(e.target.value)}>
                  {RELATIONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                电话
                <input
                  value={fPhone}
                  onChange={(e) => setFPhone(e.target.value)}
                  placeholder="紧急联系电话"
                />
              </label>
              <label>
                备注
                <input value={fNote} onChange={(e) => setFNote(e.target.value)} />
              </label>
              <button className="btn primary block" type="submit">
                保存
              </button>
            </form>
          )}
          <ul className="list-card">
            {family.map((f) => (
              <li key={f.id}>
                <h3>
                  {f.name}
                  <span className="badge soft">{f.relation}</span>
                </h3>
                <p className="meta">
                  {f.phone || '未填电话'}
                  {f.note ? ` · ${f.note}` : ''}
                </p>
                <div className="row-actions">
                  <button type="button" className="linkish" onClick={() => void onDelFamily(f.id)}>
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {family.length === 0 && !showFamilyForm && (
            <p className="muted">暂无家人关联，点击右上角 + 添加</p>
          )}
        </>
      )}

      {tab === 'hospital' && (
        <>
          <div className="page-title" style={{ marginTop: 0 }}>
            <h2 style={{ fontSize: '1.05rem', margin: 0 }}>医院关联</h2>
            <button
              type="button"
              className="btn-add"
              onClick={() => setShowHospitalForm((v) => !v)}
              aria-label={showHospitalForm ? '取消' : '添加医院'}
            >
              {showHospitalForm ? '×' : '+'}
            </button>
          </div>
          {showHospitalForm && (
            <form className="form-card" onSubmit={onAddHospital}>
              <label>
                医院名称
                <input value={hName} onChange={(e) => setHName(e.target.value)} required />
              </label>
              <label>
                科室
                <input
                  value={hDept}
                  onChange={(e) => setHDept(e.target.value)}
                  placeholder="如 呼吸内科"
                />
              </label>
              <label>
                主治医生
                <input value={hDoctor} onChange={(e) => setHDoctor(e.target.value)} />
              </label>
              <label>
                电话
                <input value={hPhone} onChange={(e) => setHPhone(e.target.value)} />
              </label>
              <label>
                地址
                <input value={hAddr} onChange={(e) => setHAddr(e.target.value)} />
              </label>
              <label>
                备注
                <input value={hNote} onChange={(e) => setHNote(e.target.value)} />
              </label>
              <button className="btn primary block" type="submit">
                保存
              </button>
            </form>
          )}
          <ul className="list-card">
            {hospitals.map((h) => (
              <li key={h.id}>
                <h3>{h.hospital_name}</h3>
                <p className="meta">
                  {[h.department, h.doctor_name && `医生 ${h.doctor_name}`, h.phone]
                    .filter(Boolean)
                    .join(' · ') || '暂无更多信息'}
                </p>
                {h.address ? <p className="meta">{h.address}</p> : null}
                {h.note ? <p style={{ margin: '6px 0 0' }}>{h.note}</p> : null}
                <div className="row-actions">
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => void onDelHospital(h.id)}
                  >
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {hospitals.length === 0 && !showHospitalForm && (
            <p className="muted">暂无医院关联，点击右上角 + 添加</p>
          )}
        </>
      )}

      {tab === 'course' && (
        <>
          <section>
            <h3 className="section-label">已开通课程</h3>
            {courses.length === 0 ? (
              <p className="muted">暂无已开通课程</p>
            ) : (
              <ul className="list-card">
                {courses.map((c) => (
                  <li key={c.id}>
                    <Link
                      to={`/courses?id=${c.id}`}
                      style={{ textDecoration: 'none', color: 'inherit' }}
                    >
                      <h3>{c.name}</h3>
                      <p className="meta">
                        {c.semester}
                        {typeof c.price === 'number' ? ` · ¥${c.price.toFixed(2)}` : ''}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section>
            <h3 className="section-label">购买记录</h3>
            {purchases.length === 0 ? (
              <p className="muted">暂无购买记录</p>
            ) : (
              <ul className="list-card">
                {purchases.map((p) => (
                  <li key={p.id}>
                    <h3>{p.course_name}</h3>
                    <p className="meta">
                      ¥{Number(p.amount).toFixed(2)} ·{' '}
                      {p.status === 'paid' ? '已支付' : p.status} ·{' '}
                      {formatDateTime(p.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}
