import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { ServiceProduct } from '../types'
import { formatPrice, mediaUrl, priceText } from '../utils'

/** 服务价格兜底值，与后端 service_products.py 的默认售价保持一致 */
const PRICE_FALLBACK = 9.9

function Cover({ src, alt }: { src?: string; alt: string }) {
  if (src) {
    return <img src={mediaUrl(src)} alt={alt} className="course-cover-img" loading="lazy" />
  }
  return <div className="course-cover-fallback" aria-hidden="true" />
}

export default function ServiceShop() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const focusId = Number(searchParams.get('id') || 0) || null

  const [items, setItems] = useState<ServiceProduct[]>([])
  const [error, setError] = useState('')
  const [activeId, setActiveId] = useState<number | null>(focusId)
  const [buying, setBuying] = useState(false)
  const [payTip, setPayTip] = useState('')

  const isAdmin = user?.role === 'admin'

  async function load() {
    const list = await api<ServiceProduct[]>('/api/service-products')
    setItems(list)
    return list
  }

  useEffect(() => {
    async function init() {
      try {
        const list = await load()
        if (focusId && list.some((x) => x.id === focusId)) {
          setActiveId(focusId)
        } else if (list.length && activeId == null) {
          setActiveId(list[0].id)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败')
      }
    }
    void init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (focusId) setActiveId(focusId)
  }, [focusId])

  const active = useMemo(
    () => items.find((x) => x.id === activeId) ?? null,
    [items, activeId],
  )

  function selectItem(id: number) {
    setActiveId(id)
    setPayTip('')
    setSearchParams(id ? { id: String(id) } : {})
  }

  async function onPurchase() {
    if (!active || active.owned || isAdmin) return
    const ok = confirm(
      `确认支付 ${formatPrice(active.price, PRICE_FALLBACK)} 购买「${active.name}」？\n（当前为模拟支付，确认即开通）`,
    )
    if (!ok) return
    setBuying(true)
    setPayTip('')
    try {
      await api(`/api/service-products/${active.id}/purchase`, { method: 'POST' })
      const list = await load()
      const updated = list.find((x) => x.id === active.id)
      setPayTip(updated?.owned ? '支付成功，服务已开通' : '支付已记录，请刷新查看')
    } catch (e) {
      setError(e instanceof Error ? e.message : '购买失败')
    } finally {
      setBuying(false)
    }
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
      <Link to="/mall" className="back-link">
        ← 返回商城
      </Link>
      <div className="page-title">
        <div>
          <h1>服务</h1>
          <p className="sub">
            {isAdmin ? '健康服务 · 管理员免费开放' : '健康服务售卖 · 标价见详情'}
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="muted">暂无在售服务</p>
      ) : (
        <>
          <div className="course-card-grid">
            {items.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`course-card${activeId === s.id ? ' active' : ''}`}
                onClick={() => selectItem(s.id)}
              >
                <div className="course-card-cover">
                  <Cover src={s.cover_url} alt={s.name} />
                  <span className="course-card-price">
                    {priceText(s.price, isAdmin, PRICE_FALLBACK)}
                  </span>
                </div>
                <div className="course-card-body">
                  <strong>{s.name}</strong>
                  <p className="meta">
                    {s.category}
                    {s.unit_label ? ` · ${s.unit_label}` : ''}
                    {isAdmin ? ' · 免费开放' : s.owned ? ' · 已开通' : ''}
                  </p>
                </div>
              </button>
            ))}
          </div>

          {active && (
            <section className="item-card course-detail">
              <div className="course-detail-cover">
                <Cover src={active.cover_url} alt={active.name} />
              </div>
              <h2>{active.name}</h2>
              <p className={`course-price-lg${isAdmin ? ' is-free' : ''}`}>
                {priceText(active.price, isAdmin, PRICE_FALLBACK)}
              </p>
              <p className="meta">
                {active.category}
                {active.unit_label ? ` · ${active.unit_label}` : ''}
                {isAdmin ? ' · 免费开放' : active.owned ? ' · 已开通' : ' · 未开通'}
              </p>
              {active.description ? (
                <p style={{ margin: '10px 0 0' }}>{active.description}</p>
              ) : (
                <p className="muted" style={{ margin: '10px 0 0' }}>
                  暂无简介
                </p>
              )}

              {active.owned || isAdmin ? (
                <p className="ok-tip" style={{ marginTop: 12 }}>
                  {isAdmin ? '管理员免费开放，无需购买' : '该服务已开通'}
                </p>
              ) : (
                <div className="course-buy-box">
                  <button
                    type="button"
                    className="btn primary block"
                    disabled={buying}
                    onClick={() => void onPurchase()}
                  >
                    {buying ? '支付中…' : `支付 ${formatPrice(active.price, PRICE_FALLBACK)} 开通`}
                  </button>
                  <p className="meta">模拟支付：确认后立即开通，后续可接真实支付通道</p>
                </div>
              )}
              {payTip ? <p className="ok-tip">{payTip}</p> : null}
            </section>
          )}
        </>
      )}
    </div>
  )
}
