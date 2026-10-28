import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import {
  disablePush,
  enablePush,
  fetchPushConfig,
  fetchPushStatus,
  isStandalone,
  pushCapability,
  registerServiceWorker,
  sendTestPush,
} from '../push'
import type {
  AppNotification,
  NotificationList,
  PushConfig,
  PushStatus,
} from '../types'
import { formatDateTime } from '../utils'

const TRIGGER_LABEL: Record<string, string> = {
  '7d': '提前 7 天',
  '1d': '提前 1 天',
  due: '到期提醒',
  recall: '学习召回',
}

function triggerLabel(key: string): string {
  return TRIGGER_LABEL[key] ?? '提醒'
}

function isIos(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
}

export default function Notifications() {
  const navigate = useNavigate()
  const capability = useMemo(() => pushCapability(), [])
  const [list, setList] = useState<NotificationList | null>(null)
  const [config, setConfig] = useState<PushConfig | null>(null)
  const [status, setStatus] = useState<PushStatus | null>(null)
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  )
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function loadInbox() {
    const data = await api<NotificationList>('/api/notifications?page=1&page_size=50')
    setList(data)
  }

  useEffect(() => {
    let alive = true
    void (async () => {
      try {
        const data = await api<NotificationList>('/api/notifications?page=1&page_size=50')
        if (alive) setList(data)
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : '消息加载失败')
      }
      try {
        const [cfg, state] = await Promise.all([fetchPushConfig(), fetchPushStatus()])
        if (!alive) return
        setConfig(cfg)
        setStatus(state)
      } catch {
        /* 推送状态失败不阻断消息列表 */
      }
      if (capability.supported) await registerServiceWorker()
    })()
    return () => {
      alive = false
    }
  }, [capability.supported])

  async function onEnable() {
    setBusy('enable')
    setError('')
    setMessage('')
    try {
      const state = await enablePush()
      setStatus(state)
      if (typeof Notification !== 'undefined') setPermission(Notification.permission)
      setMessage('已开启手机通知，可以发送一条测试通知确认。')
    } catch (e) {
      setError(e instanceof Error ? e.message : '开启失败')
    } finally {
      setBusy('')
    }
  }

  async function onDisable() {
    setBusy('disable')
    setError('')
    setMessage('')
    try {
      const state = await disablePush()
      setStatus(state)
      setMessage('已关闭本机通知；其它已授权设备不受影响。')
    } catch (e) {
      setError(e instanceof Error ? e.message : '关闭失败')
    } finally {
      setBusy('')
    }
  }

  async function onTest() {
    setBusy('test')
    setError('')
    setMessage('')
    try {
      const result = await sendTestPush()
      setStatus(await fetchPushStatus())
      if (result.sent > 0) {
        setMessage(`测试通知已发送到 ${result.sent} 台设备，请查看手机通知栏。`)
      } else {
        setError(`发送失败：${result.detail || '请确认设备通知权限已开启'}`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '测试通知发送失败')
    } finally {
      setBusy('')
    }
  }

  async function openNotification(item: AppNotification) {
    if (!item.read) {
      try {
        await api(`/api/notifications/${item.id}/read`, { method: 'POST' })
        setList((prev) =>
          prev
            ? {
                ...prev,
                unread: Math.max(0, prev.unread - 1),
                items: prev.items.map((row) =>
                  row.id === item.id ? { ...row, read: true, read_at: new Date().toISOString() } : row,
                ),
              }
            : prev,
        )
      } catch {
        /* 标记失败仍允许进入对应页面 */
      }
    }
    navigate(item.click_url || '/notifications')
  }

  async function markAllRead() {
    setBusy('read-all')
    try {
      await api('/api/notifications/read-all', { method: 'POST' })
      await loadInbox()
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    } finally {
      setBusy('')
    }
  }

  const enabledDevices = status?.subscriptions ?? 0
  const pushUsable = capability.supported && config?.enabled === true && permission !== 'denied'

  return (
    <div className="screen stack-gap">
      <div className="page-title">
        <div>
          <h1>消息通知</h1>
          <p className="sub">提醒会同时出现在这里和手机通知栏</p>
        </div>
      </div>

      <section className="card push-card">
        <div className="push-head">
          <div>
            <strong>手机通知</strong>
            <p className="muted">
              开启后，用药与复查提醒会推送到手机；点击通知可直接回到对应页面。
            </p>
          </div>
          <span className={`push-state${enabledDevices > 0 ? ' on' : ''}`}>
            {enabledDevices > 0 ? `已开启 · ${enabledDevices} 台` : '未开启'}
          </span>
        </div>

        {!capability.supported && <p className="notice-strip">{capability.reason}</p>}
        {capability.supported && config && !config.enabled && (
          <p className="notice-strip">{config.reason || '服务端未启用手机通知'}</p>
        )}
        {capability.supported && permission === 'denied' && (
          <p className="notice-strip">
            浏览器已阻止通知。请在地址栏的站点设置中允许通知，然后刷新本页。
          </p>
        )}
        {capability.supported && isIos() && !isStandalone() && (
          <p className="notice-strip">
            iPhone 需要先「添加到主屏幕」，从主屏幕打开后再开启通知（iOS 16.4 及以上）。
          </p>
        )}

        {error && <p className="error">{error}</p>}
        {message && <p className="success-text">{message}</p>}

        <div className="push-actions">
          {enabledDevices === 0 ? (
            <button
              type="button"
              className="btn primary"
              disabled={!pushUsable || busy === 'enable'}
              onClick={() => void onEnable()}
            >
              {busy === 'enable' ? '正在开启…' : '开启手机通知'}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn"
                disabled={busy === 'test'}
                onClick={() => void onTest()}
              >
                {busy === 'test' ? '发送中…' : '发送测试通知'}
              </button>
              <button
                type="button"
                className="btn ghost-danger"
                disabled={busy === 'disable'}
                onClick={() => void onDisable()}
              >
                {busy === 'disable' ? '正在关闭…' : '关闭本机通知'}
              </button>
            </>
          )}
        </div>
        <p className="push-foot">
          通知内容会显示在锁屏上，如涉及隐私，可在系统设置中关闭「通知预览」。
        </p>
      </section>

      <section className="card">
        <div className="notif-head">
          <h2>
            消息列表
            {list && list.unread > 0 && <span className="notif-unread">{list.unread}</span>}
          </h2>
          <button
            type="button"
            className="link-btn"
            disabled={!list?.unread || busy === 'read-all'}
            onClick={() => void markAllRead()}
          >
            全部已读
          </button>
        </div>

        {!list && <p className="center-msg muted">加载中…</p>}
        {list && list.items.length === 0 && (
          <p className="center-msg muted">暂无消息。开启手机通知后，提醒会出现在这里。</p>
        )}
        <div className="notif-list">
          {list?.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`notif-item${item.read ? '' : ' unread'}`}
              onClick={() => void openNotification(item)}
            >
              <span className="notif-dot" aria-hidden="true" />
              <span className="notif-main">
                <strong>{item.title}</strong>
                {item.body && <span className="notif-body">{item.body}</span>}
                <span className="notif-meta">
                  {triggerLabel(item.trigger_key)}
                  {item.course_name ? ` · ${item.course_name}` : ''} ·{' '}
                  {formatDateTime(item.created_at)}
                </span>
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}
