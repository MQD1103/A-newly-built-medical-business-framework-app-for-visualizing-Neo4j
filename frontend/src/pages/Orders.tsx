import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type {
  MallMyCourse,
  MallOrder,
  MallOrderList,
  MallRefundCheck,
  MallRefundPolicy,
} from '../types'
import { formatDate, formatDateTime, formatPrice } from '../utils'

const STATUS_LABEL: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  cancelled: '已取消',
  refund_pending: '退款处理中',
  refunded: '已退款',
  partially_refunded: '部分退款',
}

const STATUS_TONE: Record<string, string> = {
  pending: 'ok',
  paid: 'ok',
  cancelled: 'soft',
  refund_pending: 'soft',
  refunded: 'soft',
  partially_refunded: 'soft',
}

export default function Orders() {
  const [courses, setCourses] = useState<MallMyCourse[]>([])
  const [orders, setOrders] = useState<MallOrder[]>([])
  const [policy, setPolicy] = useState<MallRefundPolicy | null>(null)
  const [error, setError] = useState('')
  const [tip, setTip] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyNo, setBusyNo] = useState('')
  const [refundInfo, setRefundInfo] = useState<Record<string, MallRefundCheck>>({})

  const [code, setCode] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [courseList, orderList, policyData] = await Promise.all([
        api<MallMyCourse[]>('/api/mall/my-courses'),
        api<MallOrderList>('/api/mall/orders/mine?page_size=50'),
        api<MallRefundPolicy>('/api/mall/refund-policy'),
      ])
      setCourses(courseList)
      setOrders(orderList.items)
      setPolicy(policyData)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function doPay(order: MallOrder) {
    setBusyNo(order.order_no)
    setTip('')
    try {
      await api(`/api/mall/orders/${order.order_no}/pay`, {
        method: 'POST',
        body: JSON.stringify({ channel: 'mock' }),
      })
      setTip('支付成功，权益已开通')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '支付失败')
    } finally {
      setBusyNo('')
    }
  }

  async function doCancel(order: MallOrder) {
    if (!confirm('确定取消该订单？')) return
    setBusyNo(order.order_no)
    try {
      await api(`/api/mall/orders/${order.order_no}/cancel`, { method: 'POST' })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '取消失败')
    } finally {
      setBusyNo('')
    }
  }

  async function checkRefund(order: MallOrder) {
    setBusyNo(order.order_no)
    setTip('')
    try {
      const info = await api<MallRefundCheck>(
        `/api/mall/orders/${order.order_no}/refund-check`,
      )
      setRefundInfo((prev) => ({ ...prev, [order.order_no]: info }))
    } catch (e) {
      setError(e instanceof Error ? e.message : '退款条件查询失败')
    } finally {
      setBusyNo('')
    }
  }

  async function doRefund(order: MallOrder) {
    const reason = prompt('请填写退款原因（可留空）', '') ?? null
    if (reason === null) return
    setBusyNo(order.order_no)
    try {
      await api(`/api/mall/orders/${order.order_no}/refund`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      })
      setTip('退款申请已提交')
      setRefundInfo((prev) => {
        const next = { ...prev }
        delete next[order.order_no]
        return next
      })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '退款失败')
    } finally {
      setBusyNo('')
    }
  }

  async function redeem() {
    const value = code.trim()
    if (!value) return
    setBusyNo('redeem')
    setTip('')
    try {
      const res = await api<{ course_name: string }>('/api/mall/seats/redeem', {
        method: 'POST',
        body: JSON.stringify({ activation_code: value }),
      })
      setTip(`兑换成功：${res.course_name || '课程已开通'}`)
      setCode('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '兑换失败')
    } finally {
      setBusyNo('')
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
          <h1>我的订单</h1>
          <p className="sub">课程与服务的购买记录、退款与团购兑换</p>
        </div>
      </div>

      {tip ? <p className="ok-tip">{tip}</p> : null}

      <section>
        <h3 className="section-label">我的课程</h3>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : courses.length === 0 ? (
          <p className="muted">暂未开通课程，去商城看看吧。</p>
        ) : (
          <ul className="list-card">
            {courses.map((item) => (
              <li key={item.course.id}>
                <h3>
                  {item.course.name}
                  <span className="badge soft">
                    {item.source === 'group' ? '团购' : '已开通'}
                  </span>
                </h3>
                <p className="meta">
                  已完成 {item.completed_lessons}/{item.total_lessons} 课时
                  {item.expires_at ? ` · 有效期至 ${formatDate(item.expires_at)}` : ''}
                </p>
                <div className="progress-track" aria-label="学习进度">
                  <span
                    className="progress-fill"
                    style={{ width: `${Math.min(100, item.progress_percent)}%` }}
                  />
                </div>
                <div className="row-actions">
                  <Link
                    to={`/courses?id=${item.course.id}`}
                    className="linkish primary"
                  >
                    继续学习
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="section-label">团购 / 代买兑换</h3>
        <div className="form-card">
          <p className="meta" style={{ marginTop: 0 }}>
            输入购买人分享的激活码，开通对应课程学习权。
          </p>
          <div className="row-actions" style={{ alignItems: 'center' }}>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="输入激活码"
              aria-label="激活码"
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn primary small"
              disabled={busyNo === 'redeem' || !code.trim()}
              onClick={() => void redeem()}
            >
              {busyNo === 'redeem' ? '兑换中…' : '兑换'}
            </button>
          </div>
        </div>
      </section>

      <section>
        <h3 className="section-label">购买记录</h3>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : orders.length === 0 ? (
          <p className="muted">暂无订单</p>
        ) : (
          <ul className="list-card">
            {orders.map((order) => {
              const info = refundInfo[order.order_no]
              const busy = busyNo === order.order_no
              return (
                <li key={order.order_no}>
                  <h3>
                    {order.product_name || '商品'}
                    <span
                      className={`badge ${STATUS_TONE[order.status] ?? 'soft'}`}
                    >
                      {STATUS_LABEL[order.status] ?? order.status}
                    </span>
                    {order.quantity > 1 ? (
                      <span className="badge soft">×{order.quantity}</span>
                    ) : null}
                  </h3>
                  <p className="meta">
                    {order.product_type === 'course' ? '课程' : '服务'} ·{' '}
                    {formatDateTime(order.created_at)} · 订单号 {order.order_no}
                  </p>
                  <p className="meta">
                    实付 {formatPrice(order.amount, 0)}
                    {order.discount_amount > 0
                      ? `（原价 ${formatPrice(order.original_amount, 0)}，优惠 ${formatPrice(order.discount_amount, 0)}）`
                      : ''}
                    {order.valid_until
                      ? ` · 有效期至 ${formatDate(order.valid_until)}`
                      : ''}
                  </p>
                  {order.refund_reason ? (
                    <p className="meta">退款原因：{order.refund_reason}</p>
                  ) : null}

                  {order.seats.length > 0 ? (
                    <div className="order-seats">
                      <p className="meta">团购名额</p>
                      <ul>
                        {order.seats.map((seat) => (
                          <li key={seat.id} className="meta">
                            {seat.learner_name || '学习人'} ·{' '}
                            {seat.status === 'activated' ? '已激活' : '待激活'}
                            {seat.activation_code
                              ? ` · 激活码 ${seat.activation_code}`
                              : ''}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {info ? (
                    <div className="refund-check">
                      <p className={info.eligible ? 'ok-tip' : 'error'}>
                        {info.eligible
                          ? `可退款 ${formatPrice(info.refund_amount, 0)}`
                          : info.reason || '当前订单不满足退款条件'}
                      </p>
                      <p className="meta">{info.policy}</p>
                    </div>
                  ) : null}

                  <div className="row-actions">
                    {order.can_pay ? (
                      <>
                        <button
                          type="button"
                          className="linkish primary"
                          disabled={busy}
                          onClick={() => void doPay(order)}
                        >
                          {busy ? '处理中…' : '去支付'}
                        </button>
                        <button
                          type="button"
                          className="linkish"
                          disabled={busy}
                          onClick={() => void doCancel(order)}
                        >
                          取消订单
                        </button>
                      </>
                    ) : null}
                    {order.status === 'paid' || order.status === 'partially_refunded' ? (
                      <>
                        <button
                          type="button"
                          className="linkish"
                          disabled={busy}
                          onClick={() => void checkRefund(order)}
                        >
                          查看退款条件
                        </button>
                        {info?.eligible ? (
                          <button
                            type="button"
                            className="linkish"
                            disabled={busy}
                            onClick={() => void doRefund(order)}
                          >
                            申请退款
                          </button>
                        ) : null}
                      </>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {policy ? (
        <p className="mall-footnote">
          退款政策：{policy.policy}（购买后 {policy.window_days} 天内且学习进度不超过{' '}
          {policy.progress_limit}% 可申请；待支付订单 {policy.order_ttl_minutes} 分钟内未支付自动取消）
        </p>
      ) : null}
    </div>
  )
}
