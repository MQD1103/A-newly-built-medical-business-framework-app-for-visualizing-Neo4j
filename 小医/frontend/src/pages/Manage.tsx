import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Course, User } from '../types'
import { roleLabel } from '../utils'

export default function Manage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [users, setUsers] = useState<User[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [error, setError] = useState('')

  const [uName, setUName] = useState('')
  const [uPass, setUPass] = useState('')
  const [uFull, setUFull] = useState('')
  const [uRole, setURole] = useState('student')

  const [cName, setCName] = useState('')
  const [cSem, setCSem] = useState('COPD 系列')
  const [cOwner, setCOwner] = useState('')
  const [cDesc, setCDesc] = useState('')
  const [cPrice, setCPrice] = useState('2.99')
  const [cCover, setCCover] = useState('')

  const [enrollUser, setEnrollUser] = useState('')
  const [enrollCourse, setEnrollCourse] = useState('')

  useEffect(() => {
    if (!isAdmin) return

    async function load() {
      try {
        const [cList, uList] = await Promise.all([
          api<Course[]>('/api/courses/all'),
          api<User[]>('/api/users'),
        ])
        setCourses(cList)
        setUsers(uList)
        const owners = uList.filter((u) => u.role === 'admin' || u.role === 'teacher')
        if (owners.length) setCOwner((prev) => prev || String(owners[0].id))
        const members = uList.filter((u) => u.role === 'student')
        if (members.length) {
          setEnrollUser((prev) => prev || String(members[0].id))
        }
        if (cList.length) {
          setEnrollCourse((prev) => prev || String(cList[0].id))
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败')
      }
    }

    void load()
  }, [isAdmin])

  if (!isAdmin) return <Navigate to="/" replace />

  async function onCreateUser(e: FormEvent) {
    e.preventDefault()
    await api('/api/users', {
      method: 'POST',
      body: JSON.stringify({
        username: uName,
        password: uPass,
        full_name: uFull,
        role: uRole,
      }),
    })
    setUName('')
    setUPass('')
    setUFull('')
    setUsers(await api<User[]>('/api/users'))
  }

  async function onCreateCourse(e: FormEvent) {
    e.preventDefault()
    await api('/api/courses', {
      method: 'POST',
      body: JSON.stringify({
        name: cName,
        semester: cSem,
        teacher_id: cOwner ? Number(cOwner) : null,
        description: cDesc,
        price: Number(cPrice) || 2.99,
        cover_url: cCover.trim(),
      }),
    })
    setCName('')
    setCDesc('')
    setCPrice('2.99')
    setCCover('')
    setCourses(await api<Course[]>('/api/courses/all'))
  }

  async function onEnroll(e: FormEvent) {
    e.preventDefault()
    await api('/api/courses/enrollments', {
      method: 'POST',
      body: JSON.stringify({
        student_id: Number(enrollUser),
        course_id: Number(enrollCourse),
      }),
    })
    alert('关联成功')
  }

  if (error) return <p className="error screen">{error}</p>

  return (
    <div className="screen stack-gap">
      <Link to="/me" className="back-link">
        ← 返回我的
      </Link>
      <div className="page-title">
        <h1>管理中心</h1>
      </div>

      <form className="form-card" onSubmit={onCreateUser}>
        <h2>新建账号</h2>
        <label>
          用户账号
          <input value={uName} onChange={(e) => setUName(e.target.value)} required />
        </label>
        <label>
          密码
          <input
            type="password"
            value={uPass}
            onChange={(e) => setUPass(e.target.value)}
            required
          />
        </label>
        <label>
          姓名
          <input value={uFull} onChange={(e) => setUFull(e.target.value)} required />
        </label>
        <label>
          角色
          <select value={uRole} onChange={(e) => setURole(e.target.value)}>
            <option value="student">用户</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <button className="btn primary block" type="submit">
          创建账号
        </button>
      </form>

      <section className="item-card">
        <h3>账号列表</h3>
        <ul className="stack-gap" style={{ marginTop: 10, padding: 0, listStyle: 'none' }}>
          {users.map((u) => (
            <li key={u.id}>
              <strong>
                {u.full_name}（{u.username}）
              </strong>
              <span className="badge soft">{roleLabel(u.role)}</span>
            </li>
          ))}
        </ul>
      </section>

      <form className="form-card" onSubmit={onCreateCourse}>
        <h2>新建课程</h2>
        <label>
          课程名
          <input value={cName} onChange={(e) => setCName(e.target.value)} required />
        </label>
        <label>
          学期
          <input value={cSem} onChange={(e) => setCSem(e.target.value)} required />
        </label>
        <label>
          负责人
          <select value={cOwner} onChange={(e) => setCOwner(e.target.value)}>
            <option value="">未指定</option>
            {users
              .filter((u) => u.role === 'admin' || u.role === 'teacher')
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
          </select>
        </label>
        <label>
          价钱（元）
          <input
            type="number"
            min={0}
            step={0.01}
            value={cPrice}
            onChange={(e) => setCPrice(e.target.value)}
            required
          />
        </label>
        <label>
          封面地址（可选）
          <input
            value={cCover}
            onChange={(e) => setCCover(e.target.value)}
            placeholder="/uploads/courses/copd-1.svg"
          />
        </label>
        <label>
          简介
          <input value={cDesc} onChange={(e) => setCDesc(e.target.value)} />
        </label>
        <button className="btn primary block" type="submit">
          创建课程
        </button>
      </form>

      <section className="item-card">
        <h3>在售课程</h3>
        <ul className="list-card" style={{ marginTop: 10 }}>
          {courses.map((c) => (
            <li
              key={c.id}
              style={{
                padding: '10px 0',
                border: 0,
                boxShadow: 'none',
                display: 'flex',
                gap: 10,
                alignItems: 'center',
              }}
            >
              {c.cover_url ? (
                <img
                  src={c.cover_url}
                  alt=""
                  style={{
                    width: 56,
                    height: 36,
                    objectFit: 'cover',
                    borderRadius: 8,
                    flexShrink: 0,
                  }}
                />
              ) : null}
              <div>
                <strong>{c.name}</strong>
                <p className="meta">
                  ¥{(c.price ?? 2.99).toFixed(2)} · {c.semester}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <form className="form-card" onSubmit={onEnroll}>
        <h2>为用户关联课程</h2>
        <label>
          用户
          <select value={enrollUser} onChange={(e) => setEnrollUser(e.target.value)}>
            {users
              .filter((u) => u.role === 'student')
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}（{s.username}）
                </option>
              ))}
          </select>
        </label>
        <label>
          课程
          <select value={enrollCourse} onChange={(e) => setEnrollCourse(e.target.value)}>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <button className="btn primary block" type="submit">
          关联
        </button>
      </form>
    </div>
  )
}
