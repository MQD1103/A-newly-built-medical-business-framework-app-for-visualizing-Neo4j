import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

const entries = [
  {
    to: '/courses',
    icon: '📚',
    title: '课程',
    desc: 'COPD 系列售课，标价购买开通',
    descAdmin: 'COPD 系列课程，管理员免费开放',
    tone: 'course' as const,
    tag: '5 门单课 · 整包 7 折',
  },
  {
    to: '/supervision',
    icon: '🩺',
    title: '监督',
    desc: '健康监督与随访提醒入口',
    descAdmin: '健康监督与随访提醒入口',
    tone: 'care' as const,
    tag: '随访打卡 · 贴心守护',
  },
  {
    to: '/service-shop',
    icon: '💎',
    title: '服务',
    desc: '远程随访、康复指导等付费服务',
    descAdmin: '远程随访、康复指导，管理员免费开放',
    tone: 'service' as const,
    tag: '专业服务 · 按需开通',
  },
]

interface Product {
  id: number
  title?: string
  name?: string
  price?: number | null
  course_type?: string
  description?: string
  kind?: 'course' | 'service'
}

interface MyOrder {
  order_no: string
  status: string
  amount?: number | null
  title?: string
  created_at?: string
}

interface MyCourse {
  course_id?: number
  id?: number
  title?: string
}

interface CartEntry {
  course_id: number
  course_name?: string
  price?: number
}

interface CartPayload {
  items?: CartEntry[]
  total_amount?: number
}

interface CouponInfo {
  code: string
  title: string
  amount_off: number
  min_spend: number
  left: number
  claimed: boolean
  status?: string | null
}

interface CheckoutResult {
  count: number
  total: number
  discount: number
  paid_amount: number
}

const ORDER_STATUS: Record<string, { label: string; cls: string }> = {
  pending: { label: '待支付', cls: 'warn' },
  paid: { label: '已支付', cls: 'ok' },
  cancelled: { label: '已取消', cls: 'muted' },
  refund_pending: { label: '退款中', cls: 'warn' },
  refunded: { label: '已退款', cls: 'muted' },
}

type FilterTab = 'all' | 'course' | 'service'

export default function Mall() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [courses, setCourses] = useState<Product[]>([])
  const [services, setServices] = useState<Product[]>([])
  const [orders, setOrders] = useState<MyOrder[]>([])
  // 功能9：订单状态筛选 + 待支付订单操作
  const [orderTab, setOrderTab] = useState<'all' | 'pending' | 'paid' | 'refund'>('all')
  const [orderBusy, setOrderBusy] = useState('')
  const [myCourses, setMyCourses] = useState<MyCourse[]>([])

  // 功能1：搜索 + 筛选
  const [keyword, setKeyword] = useState('')
  const [tab, setTab] = useState<FilterTab>('all')

  // 功能2：详情弹窗
  const [detail, setDetail] = useState<Product | null>(null)
  const [buying, setBuying] = useState(false)
  const [buyMsg, setBuyMsg] = useState('')

  // 功能3：兑换码
  const [redeemOpen, setRedeemOpen] = useState(false)
  const [redeemCode, setRedeemCode] = useState('')
  const [redeemBusy, setRedeemBusy] = useState(false)
  const [redeemMsg, setRedeemMsg] = useState<{ ok: boolean; text: string } | null>(null)

  // 功能7：购物车
  const [cart, setCart] = useState<CartPayload>({ items: [], total_amount: 0 })
  const [cartOpen, setCartOpen] = useState(false)
  const [cartBusy, setCartBusy] = useState(false)
  const [checkoutMsg, setCheckoutMsg] = useState<{ ok: boolean; text: string } | null>(null)

  // 功能8：优惠券
  const [coupons, setCoupons] = useState<CouponInfo[]>([])
  const [selectedCoupon, setSelectedCoupon] = useState('')
  const [claimMsg, setClaimMsg] = useState('')

  const loadCart = () => {
    api<CartPayload>('/api/mall/cart').then(setCart).catch(() => {})
  }
  const loadCoupons = () => {
    api<{ available?: CouponInfo[] }>('/api/mall/coupons')
      .then((r) => setCoupons(r.available ?? []))
      .catch(() => {})
  }

  useEffect(() => {
    api<{ items?: Product[] }>('/api/mall/products')
      .then((r) => setCourses((r.items ?? []).filter((p) => p.course_type).map((p) => ({ ...p, kind: 'course' as const }))))
      .catch(() => {})
    api<Product[]>('/api/service-products')
      .then((list) => setServices(list.map((p) => ({ ...p, kind: 'service' as const }))))
      .catch(() => {})
    api<{ items?: MyOrder[] }>('/api/mall/orders/mine')
      .then((r) => setOrders(r.items ?? []))
      .catch(() => {})
    api<MyCourse[]>('/api/mall/my-courses')
      .then((list) => setMyCourses(list.slice(0, 4)))
      .catch(() => {})
    loadCart()
    loadCoupons()
  }, [])

  const showOrders = useMemo(
    () =>
      orders.filter((o) => {
        if (orderTab === 'all') return true
        if (orderTab === 'refund') return o.status === 'refund_pending' || o.status === 'refunded'
        return o.status === orderTab
      }),
    [orders, orderTab]
  )

  const reloadOrders = () => {
    api<{ items?: MyOrder[] }>('/api/mall/orders/mine')
      .then((r) => setOrders(r.items ?? []))
      .catch(() => {})
  }

  const payOrder = async (no: string) => {
    if (orderBusy) return
    setOrderBusy(no)
    try {
      await api(`/api/mall/orders/${no}/pay`, { method: 'POST', body: '{}' })
      reloadOrders()
      api<MyCourse[]>('/api/mall/my-courses').then((list) => setMyCourses(list.slice(0, 4))).catch(() => {})
    } catch (e) {
      alert(e instanceof Error ? e.message : '支付失败')
    } finally {
      setOrderBusy('')
    }
  }

  const cancelOrder = async (no: string) => {
    if (orderBusy || !confirm('确定取消这笔待支付订单吗？')) return
    setOrderBusy(no)
    try {
      await api(`/api/mall/orders/${no}/cancel`, { method: 'POST', body: '{}' })
      reloadOrders()
    } catch (e) {
      alert(e instanceof Error ? e.message : '取消失败')
    } finally {
      setOrderBusy('')
    }
  }

  const priceLabel = (p?: number | null) => (p == null || p <= 0 ? '免费' : `¥${p.toFixed(2)}`)
  const productName = (p: Product) => p.title || p.name || `商品 #${p.id}`
  const matchKw = (p: Product) => !keyword.trim() || productName(p).toLowerCase().includes(keyword.trim().toLowerCase())

  const showCourses = useMemo(
    () => (tab === 'service' ? [] : courses.filter(matchKw).slice(0, 4)),
    [courses, tab, keyword]
  )
  const showServices = useMemo(
    () => (tab === 'course' ? [] : services.filter(matchKw).slice(0, 4)),
    [services, tab, keyword]
  )

  const cartCount = cart.items?.length ?? 0
  const cartTotal = cart.total_amount ?? 0
  const usableCoupons = coupons.filter((c) => c.claimed && c.status === 'unused')
  const appliedCoupon = usableCoupons.find((c) => c.code === selectedCoupon)
  const couponCut = appliedCoupon && cartTotal >= appliedCoupon.min_spend
    ? Math.min(appliedCoupon.amount_off, cartTotal)
    : 0
  const cartPay = Math.max(0, cartTotal - couponCut)

  // 功能2：详情弹窗一键购买
  const buyNow = async (p: Product) => {
    if (buying) return
    setBuying(true)
    setBuyMsg('')
    try {
      const order = await api<MyOrder>('/api/mall/orders', {
        method: 'POST',
        body: JSON.stringify({ product_type: p.kind, product_id: p.id, quantity: 1 }),
      })
      await api<MyOrder>(`/api/mall/orders/${order.order_no}/pay`, { method: 'POST', body: '{}' })
      setBuyMsg('✅ 支付成功，已开通！')
      api<{ items?: MyOrder[] }>('/api/mall/orders/mine').then((r) => setOrders(r.items ?? [])).catch(() => {})
      api<MyCourse[]>('/api/mall/my-courses').then((list) => setMyCourses(list.slice(0, 4))).catch(() => {})
    } catch (e) {
      setBuyMsg(`❌ ${e instanceof Error ? e.message : '下单失败，请稍后重试'}`)
    } finally {
      setBuying(false)
    }
  }

  // 功能3：兑换码
  const doRedeem = async () => {
    const code = redeemCode.trim()
    if (!code || redeemBusy) {
      if (!code) setRedeemMsg({ ok: false, text: '请输入兑换码' })
      return
    }
    setRedeemBusy(true)
    setRedeemMsg(null)
    try {
      const r = await api<{ message?: string }>('/api/mall/seats/redeem', {
        method: 'POST',
        body: JSON.stringify({ activation_code: code }),
      })
      setRedeemMsg({ ok: true, text: r.message || '兑换成功，名额已到账！' })
      setRedeemCode('')
    } catch (e) {
      setRedeemMsg({ ok: false, text: e instanceof Error ? e.message : '兑换失败，请检查兑换码' })
    } finally {
      setRedeemBusy(false)
    }
  }

  // 功能7：加购 / 移出 / 结算
  const addToCart = async (p: Product) => {
    try {
      const r = await api<CartPayload>(`/api/mall/cart/${p.id}`, { method: 'POST', body: '{}' })
      setCart(r)
    } catch (e) {
      alert(e instanceof Error ? e.message : '加购失败')
    }
  }

  const removeFromCart = async (courseId: number) => {
    try {
      const r = await api<CartPayload>(`/api/mall/cart/${courseId}`, { method: 'DELETE' })
      setCart(r)
    } catch {}
  }

  const doCheckout = async () => {
    if (cartBusy || cartCount === 0) return
    setCartBusy(true)
    setCheckoutMsg(null)
    try {
      const r = await api<CheckoutResult>('/api/mall/checkout', {
        method: 'POST',
        body: JSON.stringify({ coupon_code: selectedCoupon || null }),
      })
      setCheckoutMsg({ ok: true, text: `✅ 结算成功！${r.count} 笔订单，优惠 ¥${r.discount.toFixed(2)}，实付 ¥${r.paid_amount.toFixed(2)}` })
      setSelectedCoupon('')
      loadCart()
      loadCoupons()
      api<{ items?: MyOrder[] }>('/api/mall/orders/mine').then((r2) => setOrders(r2.items ?? [])).catch(() => {})
      api<MyCourse[]>('/api/mall/my-courses').then((list) => setMyCourses(list.slice(0, 4))).catch(() => {})
    } catch (e) {
      setCheckoutMsg({ ok: false, text: `❌ ${e instanceof Error ? e.message : '结算失败'}` })
    } finally {
      setCartBusy(false)
    }
  }

  // 功能8：领券
  const claimCoupon = async (code: string) => {
    setClaimMsg('')
    try {
      await api(`/api/mall/coupons/claim`, { method: 'POST', body: JSON.stringify({ code }) })
      setClaimMsg(`✅ 已领取 ${code}`)
      loadCoupons()
    } catch (e) {
      setClaimMsg(`❌ ${e instanceof Error ? e.message : '领取失败'}`)
    }
  }

  return (
    <div className="screen stack-gap mall-screen">
      <section className="mall-hero">
        <div className="mall-hero-glow" aria-hidden="true" />
        <div className="mall-hero-inner">
          <span className="mall-hero-badge">小医商城</span>
          <h1>伴您健康 · 温暖每一天</h1>
          <p className="mall-hero-sub">
            {isAdmin ? '课程 · 监督 · 服务（管理员免费开放）' : '精选课程与贴心服务，陪您走好康复每一步'}
          </p>
          <div className="mall-hero-stats">
            <span>📚 6 门精品课程</span>
            <span>💎 5 项健康服务</span>
            <span>🎁 整包立享 7 折</span>
          </div>
        </div>
      </section>

      <div className="mall-toolbar">
        <div className="mall-search">
          <span className="mall-search-icon">🔍</span>
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索课程或服务..."
            className="mall-search-input"
          />
          {keyword && (
            <button type="button" className="mall-search-clear" onClick={() => setKeyword('')} aria-label="清空">×</button>
          )}
        </div>
        <div className="mall-tabs">
          {([['all', '全部'], ['course', '课程'], ['service', '服务']] as [FilterTab, string][]).map(([k, label]) => (
            <button key={k} type="button" className={`mall-tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)}>
              {label}
            </button>
          ))}
        </div>
        <button type="button" className="mall-redeem-btn" onClick={() => { setRedeemOpen(true); setRedeemMsg(null) }}>
          🎟️ 兑换码
        </button>
        {/* 功能7：购物车入口 */}
        <button type="button" className="mall-cart-btn" onClick={() => { setCartOpen(true); setCheckoutMsg(null); loadCart() }}>
          🛒 购物车
          {cartCount > 0 && <span className="mall-cart-badge">{cartCount}</span>}
        </button>
      </div>

      <div className="mall-promo">
        <span className="mall-promo-fire">🔥</span>
        <span className="mall-promo-text">限时活动：COPD 系统课整包 7 折，仅 ¥10.46，购买即享 730 天学习权</span>
        <Link to="/courses" className="mall-promo-btn">立即抢</Link>
      </div>

      <div className="mall-grid">
        {entries.map((e) => (
          <Link key={e.to} to={e.to} className={`mall-card tone-${e.tone}`}>
            <div className="mall-card-icon" aria-hidden="true">{e.icon}</div>
            <div className="mall-card-body">
              <strong>{e.title}</strong>
              <p>{isAdmin ? e.descAdmin : e.desc}</p>
              <span className="mall-card-tag">{e.tag}</span>
            </div>
            <span className="mall-card-go">进入 →</span>
          </Link>
        ))}
      </div>

      {/* 功能8：领券中心 */}
      {coupons.length > 0 && (
        <section className="mall-section">
          <div className="mall-section-head">
            <h2>🎫 领券中心</h2>
          </div>
          <div className="mall-coupon-grid">
            {coupons.map((c) => (
              <div key={c.code} className={`mall-coupon ${c.claimed ? 'claimed' : ''}`}>
                <div className="mall-coupon-left">
                  <span className="mall-coupon-amount">¥{c.amount_off}</span>
                  <span className="mall-coupon-rule">{c.min_spend > 0 ? `满${c.min_spend}可用` : '无门槛'}</span>
                </div>
                <div className="mall-coupon-body">
                  <span className="mall-coupon-title">{c.title}</span>
                  <span className="mall-coupon-code">{c.code} · 剩{c.left}张</span>
                </div>
                <button
                  type="button"
                  className="mall-coupon-claim"
                  disabled={c.claimed || c.left <= 0}
                  onClick={() => claimCoupon(c.code)}
                >
                  {c.claimed ? (c.status === 'used' ? '已用' : '已领') : '领取'}
                </button>
              </div>
            ))}
          </div>
          {claimMsg && <p className={`mall-modal-msg ${claimMsg.startsWith('✅') ? 'ok' : 'err'}`}>{claimMsg}</p>}
        </section>
      )}

      {showCourses.length > 0 && (
        <section className="mall-section">
          <div className="mall-section-head">
            <h2>🏆 热销课程</h2>
            <Link to="/courses" className="mall-section-more">全部课程 →</Link>
          </div>
          <div className="mall-rank-list">
            {showCourses.map((p, i) => (
              <div key={`c-${p.id}`} className="mall-rank-row">
                <button type="button" className="mall-rank-item" onClick={() => { setDetail(p); setBuyMsg('') }}>
                  <span className={`mall-rank-no rank-${i + 1}`}>{i + 1}</span>
                  <span className="mall-rank-name">{productName(p)}</span>
                  <span className="mall-rank-price">{priceLabel(p.price)}</span>
                </button>
                {p.kind === 'course' && p.course_type === 'single' && (p.price ?? 0) > 0 && (
                  <button type="button" className="mall-addcart" onClick={() => addToCart(p)} title="加入购物车">
                    🛒+
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {showServices.length > 0 && (
        <section className="mall-section">
          <div className="mall-section-head">
            <h2>✨ 精选服务</h2>
            <Link to="/service-shop" className="mall-section-more">全部服务 →</Link>
          </div>
          <div className="mall-svc-grid">
            {showServices.map((s) => (
              <button key={`s-${s.id}`} type="button" className="mall-svc-card" onClick={() => { setDetail(s); setBuyMsg('') }}>
                <span className="mall-svc-name">{productName(s)}</span>
                <span className="mall-svc-price">{priceLabel(s.price)}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {keyword && showCourses.length === 0 && showServices.length === 0 && (
        <div className="mall-empty">😕 没有找到「{keyword}」相关的商品</div>
      )}

      {myCourses.length > 0 && (
        <section className="mall-section">
          <div className="mall-section-head">
            <h2>🎓 我的课程</h2>
            <Link to="/courses" className="mall-section-more">继续学习 →</Link>
          </div>
          <div className="mall-mine-chips">
            {myCourses.map((c, i) => (
              <Link key={`m-${c.course_id ?? c.id ?? i}`} to={`/courses?id=${c.course_id ?? c.id}`} className="mall-mine-chip">
                {c.title || `课程 #${c.course_id ?? c.id}`}
              </Link>
            ))}
          </div>
        </section>
      )}

      {orders.length > 0 && (
        <section className="mall-section">
          <div className="mall-section-head">
            <h2>🧾 我的订单</h2>
            <div className="mall-order-tabs">
              {(
                [
                  ['all', '全部'],
                  ['pending', '待支付'],
                  ['paid', '已支付'],
                  ['refund', '退款'],
                ] as const
              ).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  className={`mall-order-tab${orderTab === k ? ' active' : ''}`}
                  onClick={() => setOrderTab(k)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {showOrders.length === 0 ? (
            <p className="muted" style={{ padding: '6px 2px' }}>该状态下暂无订单</p>
          ) : (
            <div className="mall-order-list">
              {showOrders.map((o) => {
                const st = ORDER_STATUS[o.status] ?? { label: o.status, cls: 'muted' }
                return (
                  <div key={o.order_no} className="mall-order-item">
                    <div className="mall-order-info">
                      <span className="mall-order-title">{o.title || o.order_no}</span>
                      <span className="mall-order-no">{o.order_no}</span>
                    </div>
                    <div className="mall-order-right">
                      {o.amount != null && <span className="mall-order-amount">¥{o.amount.toFixed(2)}</span>}
                      <span className={`mall-order-status ${st.cls}`}>{st.label}</span>
                      {o.status === 'pending' && (
                        <span className="mall-order-actions">
                          <button type="button" className="mall-order-btn primary" disabled={orderBusy === o.order_no} onClick={() => void payOrder(o.order_no)}>去支付</button>
                          <button type="button" className="mall-order-btn" disabled={orderBusy === o.order_no} onClick={() => void cancelOrder(o.order_no)}>取消</button>
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      )}

      <p className="mall-footnote">模拟支付环境 · 确认订单后立即开通</p>

      {/* 功能2：详情弹窗 */}
      {detail && (
        <div className="mall-modal-mask" onClick={() => setDetail(null)}>
          <div className="mall-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="mall-modal-close" onClick={() => setDetail(null)} aria-label="关闭">×</button>
            <div className={`mall-modal-banner tone-${detail.kind === 'service' ? 'service' : 'course'}`}>
              <span>{detail.kind === 'service' ? '💎' : '📚'}</span>
            </div>
            <h3 className="mall-modal-title">{productName(detail)}</h3>
            <div className="mall-modal-price">{priceLabel(detail.price)}</div>
            <p className="mall-modal-desc">
              {detail.description ||
                (detail.kind === 'service'
                  ? '专业医护团队提供的健康服务，购买后立即开通，有效期内随时使用。'
                  : 'COPD 系列精品课程，购买后获得 730 天学习权，支持随时回看。')}
            </p>
            <div className="mall-modal-perks">
              <span>✓ 模拟支付即时开通</span>
              <span>✓ 支持退款</span>
              <span>{detail.kind === 'service' ? '✓ 医护跟进' : '✓ 730 天有效'}</span>
            </div>
            {buyMsg && <p className={`mall-modal-msg ${buyMsg.startsWith('✅') ? 'ok' : 'err'}`}>{buyMsg}</p>}
            <button type="button" className="mall-modal-buy" disabled={buying} onClick={() => buyNow(detail)}>
              {buying ? '支付中...' : `立即购买 ${priceLabel(detail.price)}`}
            </button>
          </div>
        </div>
      )}

      {/* 功能3：兑换码弹窗 */}
      {redeemOpen && (
        <div className="mall-modal-mask" onClick={() => setRedeemOpen(false)}>
          <div className="mall-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="mall-modal-close" onClick={() => setRedeemOpen(false)} aria-label="关闭">×</button>
            <div className="mall-modal-banner tone-redeem"><span>🎟️</span></div>
            <h3 className="mall-modal-title">兑换码</h3>
            <p className="mall-modal-desc">输入团购或活动兑换码，名额立即到账。</p>
            <input
              className="mall-redeem-input"
              value={redeemCode}
              onChange={(e) => setRedeemCode(e.target.value)}
              placeholder="请输入兑换码"
              onKeyDown={(e) => e.key === 'Enter' && doRedeem()}
            />
            {redeemMsg && <p className={`mall-modal-msg ${redeemMsg.ok ? 'ok' : 'err'}`}>{redeemMsg.text}</p>}
            <button type="button" className="mall-modal-buy tone-redeem" disabled={redeemBusy} onClick={doRedeem}>
              {redeemBusy ? '兑换中...' : '立即兑换'}
            </button>
          </div>
        </div>
      )}

      {/* 功能7：购物车抽屉 */}
      {cartOpen && (
        <div className="mall-modal-mask" onClick={() => setCartOpen(false)}>
          <div className="mall-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="mall-drawer-head">
              <h3>🛒 我的购物车</h3>
              <button type="button" className="mall-modal-close" style={{ position: 'static' }} onClick={() => setCartOpen(false)} aria-label="关闭">×</button>
            </div>
            {cartCount === 0 ? (
              <div className="mall-empty">购物车是空的，去热销课程挑几门吧</div>
            ) : (
              <>
                <div className="mall-drawer-items">
                  {(cart.items ?? []).map((it) => (
                    <div key={it.course_id} className="mall-drawer-item">
                      <span className="mall-drawer-name">{it.course_name || `课程 #${it.course_id}`}</span>
                      <span className="mall-drawer-price">{priceLabel(it.price)}</span>
                      <button type="button" className="mall-drawer-del" onClick={() => removeFromCart(it.course_id)} title="移除">🗑</button>
                    </div>
                  ))}
                </div>
                {/* 功能8：选择优惠券 */}
                <div className="mall-drawer-coupon">
                  <span>优惠券</span>
                  <select value={selectedCoupon} onChange={(e) => setSelectedCoupon(e.target.value)}>
                    <option value="">不使用（有 {usableCoupons.length} 张可用）</option>
                    {usableCoupons.map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.title}（减¥{c.amount_off}{c.min_spend > 0 ? ` 满${c.min_spend}可用` : ''}）
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mall-drawer-total">
                  <span>合计 <b>¥{cartTotal.toFixed(2)}</b></span>
                  {couponCut > 0 && <span className="mall-drawer-cut">券 -¥{couponCut.toFixed(2)}</span>}
                  <span>实付 <b className="mall-drawer-pay">¥{cartPay.toFixed(2)}</b></span>
                </div>
                {checkoutMsg && <p className={`mall-modal-msg ${checkoutMsg.ok ? 'ok' : 'err'}`}>{checkoutMsg.text}</p>}
                <button type="button" className="mall-modal-buy" disabled={cartBusy} onClick={doCheckout}>
                  {cartBusy ? '结算中...' : `立即结算 ¥${cartPay.toFixed(2)}`}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}