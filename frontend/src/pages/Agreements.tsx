import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { AgreementInfo } from '../types'

/** 极简 Markdown 渲染：标题 / 列表 / 段落，够展示协议正文即可 */
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
    } else if (line.startsWith('**') && line.endsWith('**')) {
      nodes.push(<p key={i} className="agree-strong">{line.replaceAll('**', '')}</p>)
    } else {
      nodes.push(<p key={i}>{line.replaceAll('**', '')}</p>)
    }
  })
  flushList('last')
  return nodes
}

export default function Agreements() {
  const { type } = useParams()
  const [list, setList] = useState<AgreementInfo[]>([])
  const [doc, setDoc] = useState<AgreementInfo | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError('')
    if (type) {
      api<AgreementInfo>(`/api/agreements/${type}`)
        .then(setDoc)
        .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
        .finally(() => setLoading(false))
    } else {
      api<AgreementInfo[]>('/api/agreements')
        .then(setList)
        .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
        .finally(() => setLoading(false))
    }
  }, [type])

  const backTo = type ? '/me' : '/login'

  return (
    <div className="phone-stage">
      <div className="app-frame">
        <div className="screen stack-gap">
          <Link to={backTo} className="back-link">
            ← 返回
          </Link>

          {error && <p className="error">{error}</p>}
          {loading && <p className="center-msg muted">加载中…</p>}

          {!loading && !type && (
            <section>
              <div className="page-title">
                <div>
                  <h1>协议中心</h1>
                  <p className="sub">用户协议与隐私政策</p>
                </div>
              </div>
              <ul className="list-card">
                {list.map((a) => (
                  <li key={a.agreement_type}>
                    <Link
                      to={`/agreements/${a.agreement_type}`}
                      className="menu-row"
                    >
                      <span>
                        <h3>{a.title}</h3>
                        <p className="meta">
                          版本 {a.version} · 生效于 {a.effective_date}
                        </p>
                        <p className="meta">{a.summary}</p>
                      </span>
                      <span className="chev">›</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!loading && doc && (
            <article className="agreement-doc">
              <h2>{doc.title}</h2>
              <p className="meta">
                版本 {doc.version} · 生效于 {doc.effective_date}
              </p>
              {renderDoc(doc.content ?? '')}
            </article>
          )}
        </div>
      </div>
    </div>
  )
}
