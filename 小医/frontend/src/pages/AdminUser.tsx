import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { AdminOverview, Reminder, User } from '../types'
import { formatDateTime, mediaUrl, roleLabel } from '../utils'

/** ISO 时间 → datetime-local 输入框的值 */
function toLocalInput(iso: string): string {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function AdminUser() {
  const { user, impersonate } = useAuth()
  const isAdmin = user?.role === 'admin'
  const navigate = useNavigate()

  const [users, setUsers] = useState<User[]>([])
  const [userId, setUserId] = useState('')
  const [ov, setOv] = useState<AdminOverview | null>(null)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')

  const [rTitle, setRTitle] = useState('')
  const [rContent, setRContent] = useState('')
  const [rDue, setRDue] = useState('')
  const [rEditId, setREditId] = useState<number | null>(null)

  const [fullName, setFullName] = useState('')
  const [newPass, setNewPass] = useState('')

  // 只列非管理员：管理员本就拥有全部功能，代办没有意义
  useEffect(() => {
    if (!isAdmin) return
    void (async () => {
      try {
        const list = await api<User[]>('/api/users')
        const targets = list.filter((u) => u.role !== 'admin')
        setUsers(targets)
        // 默认选中第一个学生：课程/服务/提醒三块都能用
        const first = targets.find((u) => u.role === 'student') ?? targets[0]
        if (first) setUserId((prev) => prev || String(first.id))
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载用户失败')
      }
    })()
  }, [isAdmin])

  // 切换选中的用户时重新拉取；改资料表单的初始值也在这里同步
  useEffect(() => {
    if (!isAdmin || !userId) return
    let alive = true
    void (async () => {
      try {
        const data = await api<AdminOverview>(`/api/admin/users/${userId}/overview`)
        if (!alive) return
        setOv(data)
        setFullName(data.user.full_name)
        setError('')
      } catch (e) {
        if (!alive) return
        setError(e instanceof Error ? e.message : '加载失败')
      }
    })()
    return () => {
      alive = false
    }
  }, [isAdmin, userId])

  const reload = useCallback(async () => {
    if (!userId) return
    const data = await api<AdminOverview>(`/api/admin/users/${userId}/overview`)
    setOv(data)
  }, [userId])

  /** 所有代办操作共用的提交包装：统一报错 + 成功后刷新面板 */
  async function run(action: () => Promise<unknown>, done: string) {
    setTip('')
    try {
      await action()
      await reload()
      setTip(done)
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  function resetReminderForm() {
    setRTitle('')
    setRContent('')
    setRDue('')
    setREditId(null)
  }

  function openReminderEdit(r: Reminder) {
    setREditId(r.id)
    setRTitle(r.title)
    setRContent(r.content || '')
    setRDue(toLocalInput(r.due_at))
  }

  async function onSubmitReminder(e: FormEvent) {
    e.preventDefault()
    const body = {
      title: rTitle.trim(),
      content: rContent.trim(),
      due_at: new Date(rDue).toISOString(),
    }
    if (rEditId != null) {
      const id = rEditId
      resetReminderForm()
      await run(() => api(`/api/admin/reminders/${id}`, { method: 'PATCH', body: JSON.stringify(body) }), '已保存修改')
    } else {
      resetReminderForm()
      await run(
        () => api(`/api/admin/users/${userId}/reminders`, { method: 'POST', body: JSON.stringify(body) }),
        '已下发提醒',
      )
    }
  }

  async function onDeleteReminder(id: number) {
    if (!confirm('确定删除这条提醒？')) return
    await run(() => api(`/api/admin/reminders/${id}`, { method: 'DELETE' }), '已删除提醒')
  }

  async function onSubmitProfile(e: FormEvent) {
    e.preventDefault()
    const body: Record<string, string> = {}
    if (fullName.trim() && fullName.trim() !== ov?.user.full_name) {
      body.full_name = fullName.trim()
    }
    if (newPass) body.new_password = newPass
    if (!Object.keys(body).length) {
      setTip('')
      setError('没有需要修改的内容')
      return
    }
    await run(async () => {
      await api(`/api/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify(body) })
      // 姓名变了，下拉里的显示也要跟着变（面板本身由 reload() 刷新）
      const list = await api<User[]>('/api/users')
      setUsers(list.filter((u) => u.role !== 'admin'))
      setNewPass('')
    }, body.new_password ? '已更新资料并重置密码' : '已更新姓名')
  }

  async function onImpersonate() {
    setTip('')
    try {
      await impersonate(Number(userId))
      navigate('/')
    } catch (e) {
      setError(e instanceof Error ? e.message : '切换失败')
    }
  }

  if (!isAdmin) return <Navigate to="/" replace />

  const courses = ov?.courses ?? []
  const services = ov?.services ?? []
  const enrolledCount = courses.filter((c) => c.enrolled).length
  const ownedCount = services.filter((s) => s.owned).length

  return (
    <div className="screen stack-gap">
      <Link to="/" className="back-link">
        ← 返回首页
      </Link>
      <div className="page-title">
        <div>
          <h1>管理员代办</h1>
        </div>
      </div>

      <label className="inline-filter">
        选择用户
        <select value={userId} onChange={(e) => setUserId(e.target.value)}>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}（{u.username}）· {roleLabel(u.role)}
            </option>
          ))}
        </select>
      </label>

      {error && <p className="error">{error}</p>}
      {tip && <p className="ok-tip">{tip}</p>}

      {ov && (
        <>
          <section className="item-card">
            <div className="admin-user-head">
              {ov.user.avatar_url ? (
                <img src={mediaUrl(ov.user.avatar_url)} alt="" className="admin-user-avatar" />
              ) : null}
              <div>
                <strong>
                  {ov.user.full_name}
                  <span className="badge soft">{roleLabel(ov.user.role)}</span>
                </strong>
                <p className="meta">
                  账号 {ov.user.username} · 已开通 {enrolledCount} 门课程 / {ownedCount} 项服务
                </p>
              </div>
            </div>
            <button type="button" className="btn primary block" onClick={() => void onImpersonate()}>
              以此用户身份进入
            </button>
            <p className="meta">进入后整个界面变成该用户的视角，顶部横幅可随时退出。</p>
          </section>

          <section className="item-card">
            <h3>课程</h3>
            {ov.user.role !== 'student' ? (
              <p className="muted">该用户不是学生，课程按授课课程计算，无法在此开通。</p>
            ) : (
              <ul className="list-card" style={{ marginTop: 10 }}>
                {courses.map((c) => (
                  <li key={c.id} className="admin-row">
                    <div>
                      <strong>{c.name}</strong>
                      <p className="meta">
                        {c.semester} · ¥{(c.price ?? 2.99).toFixed(2)}
                      </p>
                    </div>
                    <div className="row-actions">
                      <span className={`badge ${c.enrolled ? 'ok' : 'soft'}`}>
                        {c.enrolled ? '已开通' : '未开通'}
                      </span>
                      {c.enrolled ? (
                        <button
                          type="button"
                          className="linkish"
                          onClick={() =>
                            void run(
                              () => api(`/api/admin/users/${userId}/courses/${c.id}`, { method: 'DELETE' }),
                              `已取消《${c.name}》`,
                            )
                          }
                        >
                          取消
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="linkish primary"
                          onClick={() =>
                            void run(
                              () =>
                                api(`/api/admin/users/${userId}/courses`, {
                                  method: 'POST',
                                  body: JSON.stringify({ course_id: c.id }),
                                }),
                              `已开通《${c.name}》`,
                            )
                          }
                        >
                          免费开通
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="item-card">
            <h3>健康服务</h3>
            <ul className="list-card" style={{ marginTop: 10 }}>
              {services.map((s) => (
                <li key={s.id} className="admin-row">
                  <div>
                    <strong>{s.name}</strong>
                    <p className="meta">
                      {s.category} · ¥{(s.price ?? 9.9).toFixed(2)}
                      {s.unit_label ? ` · ${s.unit_label}` : ''}
                    </p>
                  </div>
                  <div className="row-actions">
                    <span className={`badge ${s.owned ? 'ok' : 'soft'}`}>
                      {s.owned ? '已开通' : '未开通'}
                    </span>
                    {s.owned ? (
                      <button
                        type="button"
                        className="linkish"
                        onClick={() =>
                          void run(
                            () => api(`/api/admin/users/${userId}/services/${s.id}`, { method: 'DELETE' }),
                            `已取消「${s.name}」`,
                          )
                        }
                      >
                        取消
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="linkish primary"
                        onClick={() =>
                          void run(
                            () =>
                              api(`/api/admin/users/${userId}/services`, {
                                method: 'POST',
                                body: JSON.stringify({ service_id: s.id }),
                              }),
                            `已开通「${s.name}」`,
                          )
                        }
                      >
                        免费开通
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <form className="form-card" onSubmit={onSubmitReminder}>
            <h2>{rEditId != null ? '修改监督提醒' : '新增监督提醒'}</h2>
            <label>
              标题
              <input
                value={rTitle}
                onChange={(e) => setRTitle(e.target.value)}
                placeholder="如：两周后复查肺功能"
                required
              />
            </label>
            <label>
              提醒时间
              <input
                type="datetime-local"
                value={rDue}
                onChange={(e) => setRDue(e.target.value)}
                required
              />
            </label>
            <label>
              说明（可选）
              <textarea
                rows={3}
                value={rContent}
                onChange={(e) => setRContent(e.target.value)}
                placeholder="补充说明，可留空"
              />
            </label>
            <button className="btn primary block" type="submit">
              {rEditId != null ? '保存' : '下发给他'}
            </button>
            {rEditId != null && (
              <button type="button" className="btn block" onClick={resetReminderForm}>
                取消编辑
              </button>
            )}
          </form>

          <section className="item-card">
            <h3>他名下的监督提醒</h3>
            <ul className="list-card" style={{ marginTop: 10 }}>
              {(ov.reminders ?? []).map((r) => (
                <li key={r.id}>
                  <h3>
                    {r.title}
                    <span className={`badge ${r.status === 'overdue' ? 'danger' : 'ok'}`}>
                      {r.status === 'overdue' ? '已过期' : '待完成'}
                    </span>
                    {r.target_user_id ? <span className="badge soft">管理员下发</span> : null}
                  </h3>
                  <p className="meta">
                    {r.course_name ? `${r.course_name} · ` : ''}
                    截止 {formatDateTime(r.due_at)}
                  </p>
                  <div className="row-actions">
                    <button type="button" className="linkish primary" onClick={() => openReminderEdit(r)}>
                      修改
                    </button>
                    <button type="button" className="linkish" onClick={() => void onDeleteReminder(r.id)}>
                      删除
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            {!ov.reminders?.length && <p className="muted">暂无提醒</p>}
          </section>

          <form className="form-card" onSubmit={onSubmitProfile}>
            <h2>账号资料</h2>
            <label>
              姓名
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </label>
            <label>
              新密码（留空则不修改）
              <input
                type="password"
                value={newPass}
                onChange={(e) => setNewPass(e.target.value)}
                placeholder="直接重置，不需要对方旧密码"
              />
            </label>
            <button className="btn primary block" type="submit">
              保存
            </button>
          </form>
        </>
      )}

      {!ov && !error && <p className="muted">加载中…</p>}
    </div>
  )
}
