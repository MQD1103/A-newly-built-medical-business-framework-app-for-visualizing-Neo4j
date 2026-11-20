import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, apiUpload } from '../api'
import { useAuth } from '../auth'
import type { FriendActionResult, FriendState, FriendSummary } from '../types'
import { formatDateTime, friendActionLabel, mediaUrl, roleLabel } from '../utils'

interface OriginalPost {
  id: number
  author_name: string
  content: string
  image_urls: string[]
}

interface CommunityPost {
  id: number
  author_id: number
  author_name: string
  author_role: string
  author_avatar_url?: string
  author_friend_state: FriendState
  content: string
  image_urls: string[]
  created_at: string
  can_delete: boolean
  like_count: number
  liked_by_me: boolean
  comment_count: number
  share_count: number
  original_post_id?: number | null
  original?: OriginalPost | null
}

interface CommunityComment {
  id: number
  post_id: number
  author_id: number
  author_name: string
  author_avatar_url?: string
  content: string
  created_at: string
  can_delete: boolean
}

const MAX_IMAGES = 9

export default function Community() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<CommunityPost[]>([])
  // error 只用于首屏加载失败（会把整页换成错误屏）；其余操作用下面的行内提示
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [tip, setTip] = useState('')
  const [scope, setScope] = useState<'all' | 'friends'>('all')
  const [counts, setCounts] = useState<FriendSummary>({
    pending_requests: 0,
    unread_messages: 0,
    total: 0,
  })
  const [actedAuthors, setActedAuthors] = useState<Set<number>>(new Set())
  const [showForm, setShowForm] = useState(false)
  const [content, setContent] = useState('')
  const [imageUrls, setImageUrls] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [lightbox, setLightbox] = useState<{ urls: string[]; index: number } | null>(null)

  const [openComments, setOpenComments] = useState<number | null>(null)
  const [comments, setComments] = useState<Record<number, CommunityComment[]>>({})
  const [commentDraft, setCommentDraft] = useState<Record<number, string>>({})
  const [commentLoading, setCommentLoading] = useState(false)

  const [repostId, setRepostId] = useState<number | null>(null)
  const [repostText, setRepostText] = useState('')
  const [reposting, setReposting] = useState(false)

  async function load() {
    try {
      setItems(await api<CommunityPost[]>(`/api/community/posts?scope=${scope}`))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  async function loadSummary() {
    try {
      setCounts(await api<FriendSummary>('/api/friends/summary'))
    } catch {
      // 红点失败不能走 error，否则整页被错误屏替换
    }
  }

  useEffect(() => {
    void load()
  }, [scope])

  useEffect(() => {
    void loadSummary()
  }, [])

  useEffect(() => {
    if (!lightbox) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setLightbox(null)
      if (!lightbox) return
      if (e.key === 'ArrowRight') {
        setLightbox((cur) =>
          cur ? { ...cur, index: (cur.index + 1) % cur.urls.length } : cur,
        )
      }
      if (e.key === 'ArrowLeft') {
        setLightbox((cur) =>
          cur
            ? { ...cur, index: (cur.index - 1 + cur.urls.length) % cur.urls.length }
            : cur,
        )
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [lightbox])

  async function onPickFiles(files: FileList | null) {
    if (!files?.length) return
    const remain = MAX_IMAGES - imageUrls.length
    if (remain <= 0) {
      setActionError(`最多添加 ${MAX_IMAGES} 张照片`)
      return
    }
    const list = Array.from(files).slice(0, remain)
    setUploading(true)
    try {
      const uploaded: string[] = []
      for (const file of list) {
        if (!file.type.startsWith('image/')) continue
        const res = await apiUpload<{ url: string }>('/api/community/upload', file)
        uploaded.push(res.url)
      }
      if (uploaded.length) setImageUrls((prev) => [...prev, ...uploaded])
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  function removeImage(url: string) {
    setImageUrls((prev) => prev.filter((u) => u !== url))
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    const text = content.trim()
    if (!text && imageUrls.length === 0) {
      setActionError('请填写文字或添加照片')
      return
    }
    setSubmitting(true)
    try {
      await api('/api/community/posts', {
        method: 'POST',
        body: JSON.stringify({ content: text, image_urls: imageUrls }),
      })
      setContent('')
      setImageUrls([])
      setShowForm(false)
      await load()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '发布失败')
    } finally {
      setSubmitting(false)
    }
  }

  async function onDelete(id: number) {
    if (!confirm('确定删除这条动态？')) return
    try {
      await api(`/api/community/posts/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '删除失败')
    }
  }

  async function onToggleLike(p: CommunityPost) {
    try {
      const updated = await api<CommunityPost>(`/api/community/posts/${p.id}/like`, {
        method: 'POST',
      })
      setItems((prev) => prev.map((x) => (x.id === p.id ? updated : x)))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '操作失败')
    }
  }

  async function loadComments(postId: number) {
    setCommentLoading(true)
    try {
      const list = await api<CommunityComment[]>(
        `/api/community/posts/${postId}/comments`,
      )
      setComments((prev) => ({ ...prev, [postId]: list }))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '加载评论失败')
    } finally {
      setCommentLoading(false)
    }
  }

  async function toggleComments(postId: number) {
    if (openComments === postId) {
      setOpenComments(null)
      return
    }
    setOpenComments(postId)
    if (!comments[postId]) await loadComments(postId)
  }

  async function onSendComment(postId: number) {
    const text = (commentDraft[postId] || '').trim()
    if (!text) return
    try {
      const c = await api<CommunityComment>(`/api/community/posts/${postId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ content: text }),
      })
      setComments((prev) => ({
        ...prev,
        [postId]: [...(prev[postId] || []), c],
      }))
      setCommentDraft((prev) => ({ ...prev, [postId]: '' }))
      setItems((prev) =>
        prev.map((x) =>
          x.id === postId ? { ...x, comment_count: (x.comment_count || 0) + 1 } : x,
        ),
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '评论失败')
    }
  }

  async function onDeleteComment(postId: number, commentId: number) {
    if (!confirm('删除这条评论？')) return
    try {
      await api(`/api/community/comments/${commentId}`, { method: 'DELETE' })
      setComments((prev) => ({
        ...prev,
        [postId]: (prev[postId] || []).filter((c) => c.id !== commentId),
      }))
      setItems((prev) =>
        prev.map((x) =>
          x.id === postId
            ? { ...x, comment_count: Math.max(0, (x.comment_count || 0) - 1) }
            : x,
        ),
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '删除失败')
    }
  }

  async function onRepost() {
    if (repostId == null) return
    setReposting(true)
    try {
      await api(`/api/community/posts/${repostId}/repost`, {
        method: 'POST',
        body: JSON.stringify({ content: repostText.trim() }),
      })
      setRepostId(null)
      setRepostText('')
      await load()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '转发失败')
    } finally {
      setReposting(false)
    }
  }

  async function onAddFriend(authorId: number) {
    setTip('')
    setActionError('')
    try {
      const res = await api<FriendActionResult>('/api/friends/requests', {
        method: 'POST',
        body: JSON.stringify({ user_id: authorId }),
      })
      const accepted = res.status === 'accepted'
      setTip(accepted ? '你们已成为好友' : '申请已发送，等待对方同意')
      setActedAuthors((prev) => new Set(prev).add(authorId))
      // 同一作者可能有多条动态，按 author_id 一起更新
      setItems((prev) =>
        prev.map((x) =>
          x.author_id === authorId
            ? { ...x, author_friend_state: accepted ? 'friends' : 'pending_out' }
            : x,
        ),
      )
      void loadSummary()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '操作失败')
    }
  }

  function renderPhotos(urls: string[]) {
    if (!urls?.length) return null
    return (
      <div className={`community-photo-grid view count-${Math.min(urls.length, 9)}`}>
        {urls.map((url, idx) => (
          <button
            key={url}
            type="button"
            className="community-photo-cell"
            onClick={() => setLightbox({ urls, index: idx })}
          >
            <img src={mediaUrl(url)} alt="" loading="lazy" />
          </button>
        ))}
      </div>
    )
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
      <div className="page-title">
        <div>
          <h1>社区</h1>
          <p className="sub">小医社区 · {user?.full_name}</p>
        </div>
        <div className="page-title-actions">
          <button
            type="button"
            className="btn small"
            onClick={() => navigate('/friends')}
            title="好友与私信"
          >
            好友
            {counts.total > 0 && <span className="badge danger">{counts.total}</span>}
          </button>
          <button
            type="button"
            className="btn-add"
            onClick={() => setShowForm((v) => !v)}
            aria-label={showForm ? '取消发布' : '发布动态'}
            title={showForm ? '取消' : '发布'}
          >
            {showForm ? '×' : '+'}
          </button>
        </div>
      </div>

      <div className="link-tabs two">
        {(
          [
            ['all', '全部'],
            ['friends', '好友'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`link-tab${scope === key ? ' active' : ''}`}
            onClick={() => setScope(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {actionError && (
        <p className="error">
          {actionError}{' '}
          <button
            type="button"
            className="linkish"
            onClick={() => setActionError('')}
          >
            关闭
          </button>
        </p>
      )}
      {tip && <p className="ok-tip">{tip}</p>}

      {showForm && (
        <form className="form-card" onSubmit={onCreate}>
          <h2>发布动态</h2>
          <label>
            说点什么
            <textarea
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="经验分享、互助提问…都可以发（可只发照片）"
              maxLength={2000}
            />
          </label>

          <div className="community-compose-photos">
            <div className="community-photo-grid compose">
              {imageUrls.map((url) => (
                <div key={url} className="community-photo-cell">
                  <img src={url} alt="" />
                  <button
                    type="button"
                    className="community-photo-remove"
                    onClick={() => removeImage(url)}
                    aria-label="移除照片"
                  >
                    ×
                  </button>
                </div>
              ))}
              {imageUrls.length < MAX_IMAGES && (
                <button
                  type="button"
                  className="community-photo-add"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                >
                  {uploading ? '…' : '+'}
                  <span>照片</span>
                </button>
              )}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
              hidden
              onChange={(e) => void onPickFiles(e.target.files)}
            />
            <p className="meta">最多 {MAX_IMAGES} 张，单张不超过 5MB</p>
          </div>

          <button
            className="btn primary block"
            type="submit"
            disabled={submitting || uploading}
          >
            {submitting ? '发布中…' : '发布'}
          </button>
        </form>
      )}

      <ul className="list-card community-feed">
        {items.map((p) => (
          <li key={p.id}>
            <div className="community-post-head">
              <div className="community-author">
                {p.author_avatar_url ? (
                  <img src={mediaUrl(p.author_avatar_url)} alt="" className="community-avatar" />
                ) : (
                  <span className="community-avatar fallback">
                    {(p.author_name || '用').slice(0, 1)}
                  </span>
                )}
                <div>
                  <strong>{p.author_name || '用户'}</strong>
                  <span className="badge soft">{roleLabel(p.author_role)}</span>
                  {p.original_post_id ? (
                    <span className="badge soft">转发</span>
                  ) : null}
                  {p.author_friend_state === 'friends' ? (
                    <span className="badge soft">已是好友</span>
                  ) : friendActionLabel(
                      p.author_friend_state,
                      actedAuthors.has(p.author_id),
                    ) ? (
                    <button
                      type="button"
                      className="linkish primary"
                      onClick={(e) => {
                        e.stopPropagation()
                        void onAddFriend(p.author_id)
                      }}
                    >
                      {friendActionLabel(
                        p.author_friend_state,
                        actedAuthors.has(p.author_id),
                      )}
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
            {p.content ? <p className="community-post-body">{p.content}</p> : null}
            {p.original && (
              <div className="community-original">
                <p className="meta">@{p.original.author_name || '用户'}</p>
                {p.original.content ? (
                  <p className="community-post-body">{p.original.content}</p>
                ) : null}
                {renderPhotos(p.original.image_urls || [])}
              </div>
            )}
            {!p.original && renderPhotos(p.image_urls || [])}

            <div className="community-actions">
              <button
                type="button"
                className={`c-act${p.liked_by_me ? ' on' : ''}`}
                onClick={() => void onToggleLike(p)}
              >
                {p.liked_by_me ? '已赞' : '点赞'} {p.like_count || 0}
              </button>
              <button
                type="button"
                className={`c-act${openComments === p.id ? ' on' : ''}`}
                onClick={() => void toggleComments(p.id)}
              >
                评论 {p.comment_count || 0}
              </button>
              <button
                type="button"
                className="c-act"
                onClick={() => {
                  setRepostId(p.original_post_id || p.id)
                  setRepostText('')
                }}
              >
                转发 {p.share_count || 0}
              </button>
              {p.can_delete && (
                <button type="button" className="linkish" onClick={() => void onDelete(p.id)}>
                  删除
                </button>
              )}
            </div>
            <p className="meta" style={{ marginTop: 6 }}>
              {formatDateTime(p.created_at)}
            </p>

            {openComments === p.id && (
              <div className="community-comments">
                {commentLoading && !comments[p.id] ? (
                  <p className="muted">加载中…</p>
                ) : (
                  <ul>
                    {(comments[p.id] || []).map((c) => (
                      <li key={c.id}>
                        <strong>{c.author_name || '用户'}</strong>
                        <span>{c.content}</span>
                        <em>{formatDateTime(c.created_at)}</em>
                        {c.can_delete && (
                          <button
                            type="button"
                            className="linkish"
                            onClick={() => void onDeleteComment(p.id, c.id)}
                          >
                            删
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {(comments[p.id] || []).length === 0 && !commentLoading && (
                  <p className="muted">暂无评论</p>
                )}
                <div className="comment-compose">
                  <input
                    value={commentDraft[p.id] || ''}
                    onChange={(e) =>
                      setCommentDraft((prev) => ({ ...prev, [p.id]: e.target.value }))
                    }
                    placeholder="写评论…"
                    maxLength={1000}
                  />
                  <button
                    type="button"
                    className="btn small primary"
                    onClick={() => void onSendComment(p.id)}
                  >
                    发送
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      {items.length === 0 && (
        <p className="muted">
          {scope === 'friends'
            ? '好友暂无动态，切到「全部」看看，或先去加几个好友'
            : '还没有动态，点击右上角 + 发一条吧'}
        </p>
      )}

      {repostId != null && (
        <div className="repost-mask" role="dialog" aria-modal="true">
          <div className="repost-sheet">
            <h3>转发动态</h3>
            <textarea
              rows={3}
              value={repostText}
              onChange={(e) => setRepostText(e.target.value)}
              placeholder="说点什么（可选）"
              maxLength={500}
            />
            <div className="repost-actions">
              <button type="button" className="btn small" onClick={() => setRepostId(null)}>
                取消
              </button>
              <button
                type="button"
                className="btn small primary"
                disabled={reposting}
                onClick={() => void onRepost()}
              >
                {reposting ? '转发中…' : '转发'}
              </button>
            </div>
          </div>
        </div>
      )}

      {lightbox && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="查看照片"
          onClick={() => setLightbox(null)}
        >
          <button
            type="button"
            className="lightbox-close"
            aria-label="关闭"
            onClick={() => setLightbox(null)}
          >
            ×
          </button>
          {lightbox.urls.length > 1 && (
            <>
              <button
                type="button"
                className="lightbox-nav prev"
                aria-label="上一张"
                onClick={(e) => {
                  e.stopPropagation()
                  setLightbox((cur) =>
                    cur
                      ? {
                          ...cur,
                          index: (cur.index - 1 + cur.urls.length) % cur.urls.length,
                        }
                      : cur,
                  )
                }}
              >
                ‹
              </button>
              <button
                type="button"
                className="lightbox-nav next"
                aria-label="下一张"
                onClick={(e) => {
                  e.stopPropagation()
                  setLightbox((cur) =>
                    cur ? { ...cur, index: (cur.index + 1) % cur.urls.length } : cur,
                  )
                }}
              >
                ›
              </button>
            </>
          )}
          <img
            src={lightbox.urls[lightbox.index]}
            alt=""
            className="lightbox-img"
            onClick={(e) => e.stopPropagation()}
          />
          {lightbox.urls.length > 1 && (
            <p className="lightbox-counter">
              {lightbox.index + 1} / {lightbox.urls.length}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
