import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiUrl, getToken } from '../api'
import { useAuth } from '../auth'
import { mediaUrl, roleLabel, REPO_URL } from '../utils'

export default function Me() {
  const { user, logout, refresh } = useAuth()
  const canManage = user?.role === 'admin'
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  async function onPickAvatar(file: File | null) {
    if (!file) return
    setError('')
    setUploading(true)
    try {
      const body = new FormData()
      body.append('file', file)
      const res = await fetch(apiUrl('/api/auth/avatar'), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${getToken() ?? ''}`,
        },
        body,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || '上传失败')
      }
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="screen">
      <header className="profile-hero">
        <button
          type="button"
          className="avatar-btn"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          title="更换头像"
        >
          {user?.avatar_url ? (
            <img src={mediaUrl(user.avatar_url)} alt="" className="avatar-img" />
          ) : (
            <div className="avatar orb-fallback">
              {(user?.full_name?.[0] ?? '用').slice(0, 1)}
            </div>
          )}
          <span className="avatar-edit">{uploading ? '…' : '换'}</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          hidden
          onChange={(e) => void onPickAvatar(e.target.files?.[0] ?? null)}
        />
        <div>
          <h1>{user?.full_name}</h1>
          <p>
            {roleLabel(user?.role ?? '')} · {user?.username}
          </p>
          <p className="meta">点击头像可更换</p>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <section className="menu-card">
        {canManage && (
          <Link to="/manage" className="menu-row">
            <span>管理中心</span>
            <span className="chev">›</span>
          </Link>
        )}
        <Link to="/profile" className="menu-row">
          <span>修改资料</span>
          <span className="chev">›</span>
        </Link>
        <Link to="/health-profile" className="menu-row">
          <span className="menu-row-main">
            <span>🩺 个人健康档案</span>
            <span className="meta">诊断 · 肺功能分级 · 用药 · 紧急联系人</span>
          </span>
          <span className="chev">›</span>
        </Link>
        <Link to="/toolkit" className="menu-row">
          <span>学习工具箱 · 量表 / 记录表 / 手册</span>
          <span className="chev">›</span>
        </Link>
        <Link to="/family" className="menu-row">
          <span>👨‍👩‍👧 家属照护专区</span>
          <span className="chev">›</span>
        </Link>
        <Link to="/notifications" className="menu-row">
          <span>消息通知</span>
          <span className="chev">›</span>
        </Link>
        <Link to="/notices" className="menu-row">
          <span>通知公告</span>
          <span className="chev">›</span>
        </Link>
        <a
          className="menu-row menu-row-link"
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
        >
          <span className="menu-row-main">
            <span>GitHub 仓库</span>
            <span className="meta">源码、提交记录与更新日志</span>
          </span>
          <span className="chev">↗</span>
        </a>
      </section>

      <button type="button" className="btn block ghost-danger" onClick={logout}>
        退出登录
      </button>
    </div>
  )
}
