import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { AgreementInfo, ConsentStatus } from '../types'

/**
 * 协议确认门：登录后检查是否已同意全部现行版本的《用户协议》与《隐私政策》，
 * 有未同意项时全屏遮罩，同意前无法使用任何功能。
 *
 * 挂在 Layout 内，因此身份切换（impersonate）到未同意用户时同样会触发。
 */
export default function ConsentGate() {
  const { logout } = useAuth()
  const [status, setStatus] = useState<ConsentStatus | null>(null)
  const [docs, setDocs] = useState<Record<string, AgreementInfo>>({})
  const [activeType, setActiveType] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const check = useCallback(async () => {
    try {
      const s = await api<ConsentStatus>('/api/consents/me')
      setStatus(s)
      if (s.pending.length > 0) setActiveType((t) => t ?? s.pending[0])
    } catch {
      // 拉取失败不阻塞使用（可能是网络抖动）；下次进入页面再查
      setStatus(null)
    }
  }, [])

  useEffect(() => {
    void check()
  }, [check])

  // 弹窗出现时预取各协议的摘要与全文
  useEffect(() => {
    if (!status || status.pending.length === 0) return
    status.pending.forEach((t) => {
      if (docs[t]) return
      api<AgreementInfo>(`/api/agreements/${t}`)
        .then((d) => setDocs((prev) => ({ ...prev, [t]: d })))
        .catch(() => undefined)
    })
  }, [status, docs])

  if (!status || status.pending.length === 0) return null

  const current = activeType ? docs[activeType] : null

  async function acceptAll() {
    setBusy(true)
    setError('')
    try {
      for (const t of status!.pending) {
        await api('/api/consent', {
          method: 'POST',
          body: JSON.stringify({ agreement_type: t }),
        })
      }
      setStatus((s) => (s ? { ...s, pending: [] } : s))
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败，请重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="consent-mask" role="dialog" aria-modal="true">
      <div className="consent-card">
        <h2>欢迎使用小医</h2>
        <p className="consent-lead">
          请阅读并同意以下协议后继续使用：
        </p>

        <div className="consent-tabs">
          {status.pending.map((t) => (
            <button
              key={t}
              type="button"
              className={`consent-tab${activeType === t ? ' active' : ''}`}
              onClick={() => setActiveType(t)}
            >
              {docs[t]?.title ?? (t === 'user_agreement' ? '用户协议' : '隐私政策')}
            </button>
          ))}
        </div>

        <div className="consent-body">
          {current ? (
            <>
              <p className="meta">
                版本 {current.version} · 生效于 {current.effective_date}
              </p>
              <p className="consent-summary">{current.summary}</p>
              <details className="consent-full">
                <summary>查看全文</summary>
                <div className="agreement-doc">{renderDoc(current.content ?? '')}</div>
              </details>
            </>
          ) : (
            <p className="muted">加载中…</p>
          )}
        </div>

        {error && <p className="error">{error}</p>}

        <button
          type="button"
          className="btn primary block"
          disabled={busy}
          onClick={() => void acceptAll()}
        >
          {busy ? '提交中…' : '我已阅读并同意上述协议'}
        </button>
        <div className="consent-foot">
          <button
            type="button"
            className="linkish"
            onClick={() => {
              // 不同意则退出登录，回到登录页
              logout()
            }}
          >
            不同意并退出
          </button>
          <Link to="/agreements" className="linkish">
            在独立页面查看
          </Link>
        </div>
      </div>
    </div>
  )
}

/** 与 Agreements 页共用：极简 Markdown 渲染（标题 / 有序列表 / 段落） */
function renderDoc(content: string) {
  const lines = content.split('\n')
  const nodes: React.ReactNode[] = []
  let list: string[] = []

  function flushList(key: string) {
    if (list.length === 0) return
    nodes.push(
      <ol key={key} className="agree-ol">
        {list.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ol>,
    )
    list = []
  }

  lines.forEach((raw, i) => {
    const line = raw.trim()
    if (!line) {
      flushList(`l${i}`)
      return
    }
    if (/^\d+\.\s/.test(line)) {
      list.push(line.replace(/^\d+\.\s*/, ''))
      return
    }
    flushList(`l${i}`)
    if (line.startsWith('### ')) {
      nodes.push(<h4 key={i}>{line.slice(4)}</h4>)
    } else if (line.startsWith('## ')) {
      nodes.push(<h3 key={i}>{line.slice(3)}</h3>)
    } else if (line.startsWith('# ')) {
      nodes.push(<h2 key={i}>{line.slice(2)}</h2>)
    } else {
      nodes.push(<p key={i}>{line.replaceAll('**', '')}</p>)
    }
  })
  flushList('last')
  return nodes
}
