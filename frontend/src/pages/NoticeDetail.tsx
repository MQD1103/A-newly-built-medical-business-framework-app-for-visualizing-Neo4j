import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { Notice } from '../types'
import { audienceLabel, formatDateTime } from '../utils'

export default function NoticeDetail() {
  const { id } = useParams()
  const [notice, setNotice] = useState<Notice | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api<Notice>(`/api/notices/${id}`)
      .then(setNotice)
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) return <p className="error screen">{error}</p>
  if (!notice) return <p className="muted screen">加载中…</p>

  return (
    <div className="screen">
      <Link to="/notices" className="back-link">
        ← 返回
      </Link>
      <article className="item-card">
        <h1 style={{ margin: 0, fontSize: '1.3rem' }}>
          {notice.title}
          {notice.is_urgent ? <span className="badge danger">紧急</span> : null}
        </h1>
        <p className="meta">
          {notice.author_name} · {formatDateTime(notice.created_at)} ·{' '}
          {audienceLabel(notice.audience)}
        </p>
        <div className="article-body">{notice.body}</div>
      </article>
    </div>
  )
}
