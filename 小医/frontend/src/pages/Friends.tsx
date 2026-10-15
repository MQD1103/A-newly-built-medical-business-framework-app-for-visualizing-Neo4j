import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type {
  Friend,
  FriendActionResult,
  FriendMessage,
  FriendRequestItem,
  FriendUser,
} from '../types'
import { formatDateTime, friendActionLabel, mediaUrl, roleLabel } from '../utils'

type Tab = 'friends' | 'requests' | 'search'

const POLL_MS = 5000

/** 好友头像 + 姓名 + 账号（三处列表共用） */
function FriendHead({ person, extra }: { person: FriendUser; extra?: string }) {
  return (
    <div className="friend-row-main">
      {person.avatar_url ? (
        <img src={mediaUrl(person.avatar_url)} alt="" className="community-avatar" />
      ) : (
        <span className="community-avatar fallback">
          {(person.full_name || '用').slice(0, 1)}
        </span>
      )}
      <div style={{ minWidth: 0 }}>
        <strong>{person.full_name || person.username}</strong>
        <span className="badge soft">{roleLabel(person.role)}</span>
        <p className="meta friend-last">
          @{person.username}
          {extra ? ` · ${extra}` : ''}
        </p>
      </div>
    </div>
  )
}

export default function Friends() {
  const { user } = useAuth()

  const [tab, setTab] = useState<Tab>('friends')
  const [friends, setFriends] = useState<Friend[]>([])
  const [incoming, setIncoming] = useState<FriendRequestItem[]>([])
  const [outgoing, setOutgoing] = useState<FriendRequestItem[]>([])
  const [loading, setLoading] = useState(true)

  const [q, setQ] = useState('')
  const [results, setResults] = useState<FriendUser[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [actedResults, setActedResults] = useState<Set<number>>(new Set())

  const [chatWith, setChatWith] = useState<FriendUser | null>(null)
  const [messages, setMessages] = useState<FriendMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const busyRef = useRef(false)

  const [tip, setTip] = useState('')
  // 行内错误：本页任何错误都不整页替换
  const [error, setError] = useState('')

  async function reload() {
    const [f, inc, out] = await Promise.all([
      api<Friend[]>('/api/friends'),
      api<FriendRequestItem[]>('/api/friends/requests'),
      api<FriendRequestItem[]>('/api/friends/requests/sent'),
    ])
    setFriends(f)
    setIncoming(inc)
    setOutgoing(out)
  }

  useEffect(() => {
    reload()
      .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  async function run(action: () => Promise<unknown>, done: string) {
    setTip('')
    setError('')
    try {
      await action()
      await reload()
      setTip(done)
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  function requestFriend(userId: number) {
    return api<FriendActionResult>('/api/friends/requests', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    })
  }

  function removeRelation(userId: number) {
    return api(`/api/friends/${userId}`, { method: 'DELETE' })
  }

  async function onSearch(e: FormEvent) {
    e.preventDefault()
    const term = q.trim()
    setTip('')
    setError('')
    if (!term) {
      setResults(null)
      return
    }
    setSearching(true)
    try {
      setResults(await api<FriendUser[]>(`/api/friends/search?q=${encodeURIComponent(term)}`))
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索失败')
    } finally {
      setSearching(false)
    }
  }

  async function onSearchAdd(person: FriendUser) {
    setTip('')
    setError('')
    try {
      const res = await requestFriend(person.user_id)
      setActedResults((prev) => new Set(prev).add(person.user_id))
      setResults((prev) =>
        prev
          ? prev.map((x) =>
              x.user_id === person.user_id
                ? { ...x, friend_state: res.status === 'accepted' ? 'friends' : 'pending_out' }
                : x,
            )
          : prev,
      )
      setTip(res.status === 'accepted' ? '你们已成为好友' : '申请已发送，等待对方同意')
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  async function loadMessages(otherId: number, silent = false) {
    if (busyRef.current) return
    busyRef.current = true
    try {
      const list = await api<FriendMessage[]>(`/api/friends/${otherId}/messages`)
      setMessages((prev) =>
        prev.length === list.length && prev.at(-1)?.id === list.at(-1)?.id ? prev : list,
      )
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : '加载聊天记录失败')
    } finally {
      busyRef.current = false
    }
  }

  async function openChat(person: FriendUser) {
    setChatWith(person)
    setMessages([])
    setDraft('')
    setError('')
    setTip('')
    await loadMessages(person.user_id)
    setTimeout(() => bottomRef.current?.scrollIntoView({ block: 'end' }), 0)
  }

  function closeChat() {
    setChatWith(null)
    setMessages([])
    // 重拉一次让未读角标归零
    void reload().catch(() => undefined)
  }

  // 只在聊天打开时轮询
  useEffect(() => {
    if (!chatWith) return
    const timer = setInterval(() => {
      void loadMessages(chatWith.user_id, true)
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [chatWith])

  async function onSend() {
    if (!chatWith) return
    const text = draft.trim()
    if (!text) return
    setSending(true)
    setError('')
    try {
      await api<FriendMessage>(`/api/friends/${chatWith.user_id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content: text }),
      })
      setDraft('')
      await loadMessages(chatWith.user_id)
      setTimeout(() => bottomRef.current?.scrollIntoView({ block: 'end' }), 0)
    } catch (e) {
      setError(e instanceof Error ? e.message : '发送失败')
    } finally {
      setSending(false)
    }
  }

  if (chatWith) {
    return (
      <div className="screen stack-gap">
        <div className="page-title">
          <div>
            <button type="button" className="linkish primary" onClick={closeChat}>
              ← 返回好友列表
            </button>
            <h1 style={{ fontSize: '1.15rem', margin: '6px 0 0' }}>
              {chatWith.full_name || chatWith.username}
              <span className="badge soft">{roleLabel(chatWith.role)}</span>
            </h1>
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {messages.length === 0 && !error && (
          <p className="muted">还没有聊天记录，打个招呼吧</p>
        )}
        <ul className="chat-list">
          {messages.map((m) => (
            <li key={m.id} className={`chat-bubble ${m.mine ? 'me' : 'them'}`}>
              {m.content}
              <span className="chat-time">{formatDateTime(m.created_at)}</span>
            </li>
          ))}
        </ul>
        <div ref={bottomRef} />

        <div className="chat-compose">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="发条消息…"
            maxLength={1000}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void onSend()
            }}
          />
          <button
            type="button"
            className="btn small primary"
            disabled={sending || !draft.trim()}
            onClick={() => void onSend()}
          >
            {sending ? '发送中…' : '发送'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="screen stack-gap">
      <Link to="/community" className="back-link">
        ← 返回社区
      </Link>

      <div className="page-title">
        <div>
          <h1>好友</h1>
          <p className="sub">好友 · 申请 · 搜索</p>
        </div>
      </div>

      <div className="link-tabs">
        {(
          [
            ['friends', '好友'],
            ['requests', '申请'],
            ['search', '搜索'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`link-tab${tab === key ? ' active' : ''}`}
            onClick={() => setTab(key)}
          >
            {label}
            {key === 'requests' && incoming.length > 0 && (
              <span className="badge danger">{incoming.length}</span>
            )}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {tip && <p className="ok-tip">{tip}</p>}

      {tab === 'friends' && (
        <>
          {loading && <p className="muted">加载中…</p>}
          {!loading && friends.length === 0 && (
            <p className="muted">好友为空，去「搜索」或在社区动态里点「加好友」</p>
          )}
          <ul className="list-card">
            {friends.map((f) => (
              <li key={f.user_id}>
                <div className="friend-row">
                  <FriendHead
                    person={f}
                    extra={f.last_message ? f.last_message : '还没有聊天记录'}
                  />
                  <div className="row-actions">
                    {f.unread_count > 0 && (
                      <span className="badge danger">{f.unread_count}</span>
                    )}
                    <button
                      type="button"
                      className="linkish primary"
                      onClick={() => void openChat(f)}
                    >
                      私信
                    </button>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => {
                        if (
                          confirm(`删除好友「${f.full_name || f.username}」？聊天记录会保留`)
                        ) {
                          void run(
                            () => removeRelation(f.user_id),
                            `已删除好友「${f.full_name || f.username}」`,
                          )
                        }
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {tab === 'requests' && (
        <>
          <h3 className="section-label">待处理（{incoming.length}）</h3>
          {incoming.length === 0 && <p className="muted">暂无待处理申请</p>}
          <ul className="list-card">
            {incoming.map((r) => (
              <li key={r.request_id}>
                <div className="friend-row">
                  <FriendHead person={r} extra={formatDateTime(r.created_at)} />
                  <div className="row-actions">
                    <button
                      type="button"
                      className="linkish primary"
                      onClick={() =>
                        void run(
                          () =>
                            api(`/api/friends/requests/${r.request_id}/accept`, {
                              method: 'POST',
                            }),
                          `已同意「${r.full_name || r.username}」的好友申请`,
                        )
                      }
                    >
                      同意
                    </button>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() =>
                        void run(
                          () => removeRelation(r.user_id),
                          '已拒绝该申请',
                        )
                      }
                    >
                      拒绝
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <h3 className="section-label">我发出的（{outgoing.length}）</h3>
          {outgoing.length === 0 && <p className="muted">没有等待对方验证的申请</p>}
          <ul className="list-card">
            {outgoing.map((r) => (
              <li key={r.request_id}>
                <div className="friend-row">
                  <FriendHead person={r} extra={formatDateTime(r.created_at)} />
                  <div className="row-actions">
                    <button
                      type="button"
                      className="linkish"
                      onClick={() =>
                        void run(() => removeRelation(r.user_id), '已撤销申请')
                      }
                    >
                      撤销
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <p className="meta">对方同意后会自动出现在好友列表里。</p>
        </>
      )}

      {tab === 'search' && (
        <>
          <form className="form-card" onSubmit={onSearch}>
            <label>
              账号或姓名
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="输入账号或姓名搜索"
              />
            </label>
            <button className="btn primary block" type="submit" disabled={searching}>
              {searching ? '搜索中…' : '搜索'}
            </button>
          </form>

          {results === null && <p className="muted">输入账号或姓名开始搜索</p>}
          {results !== null && results.length === 0 && (
            <p className="muted">没有找到相关用户</p>
          )}
          <ul className="list-card">
            {(results || []).map((u) => {
              const label = friendActionLabel(
                u.friend_state,
                actedResults.has(u.user_id),
              )
              return (
                <li key={u.user_id}>
                  <div className="friend-row">
                    <FriendHead person={u} />
                    <div className="row-actions">
                      {label ? (
                        <button
                          type="button"
                          className="linkish primary"
                          onClick={() => void onSearchAdd(u)}
                          disabled={u.friend_state === 'pending_out'}
                        >
                          {label}
                        </button>
                      ) : (
                        <span className="badge soft">已是好友</span>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </>
      )}

      <p className="meta">当前身份：{user?.full_name}</p>
    </div>
  )
}
