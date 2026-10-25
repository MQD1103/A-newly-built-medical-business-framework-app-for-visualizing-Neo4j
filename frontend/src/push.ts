/**
 * 手机通知（Web Push）的前端封装。
 *
 * 需要安全上下文（HTTPS 或 localhost）才能注册 Service Worker；
 * iOS 需要先「添加到主屏幕」，再在应用内开启通知。
 */
import { api } from './api'
import type { PushConfig, PushStatus, PushTestResult } from './types'

export interface PushCapability {
  supported: boolean
  reason: string
}

/** 本设备的订阅地址；浏览器订阅丢失时仍可据此清理服务端记录 */
const PUSH_ENDPOINT_KEY = 'edu_push_endpoint'

const isIos = () =>
  typeof navigator !== 'undefined' && /iPad|iPhone|iPod/.test(navigator.userAgent)

/** iOS 是否以「主屏幕应用」方式打开 */
export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  if (window.matchMedia?.('(display-mode: standalone)').matches) return true
  return (navigator as Navigator & { standalone?: boolean }).standalone === true
}

export function pushCapability(): PushCapability {
  if (typeof window === 'undefined') {
    return { supported: false, reason: '当前环境不支持通知' }
  }
  if (!window.isSecureContext) {
    return {
      supported: false,
      reason: '手机通知需要 HTTPS 安全环境（本地调试可用 localhost）',
    }
  }
  if (isIos() && !isStandalone()) {
    // iOS 只在「主屏幕应用」中开放推送，先给出可执行的提示
    return {
      supported: false,
      reason: 'iPhone / iPad 请先用浏览器菜单「添加到主屏幕」，再从主屏幕打开本应用',
    }
  }
  if (!('serviceWorker' in navigator)) {
    return { supported: false, reason: '当前浏览器不支持 Service Worker' }
  }
  if (!('PushManager' in window)) {
    return { supported: false, reason: '当前浏览器不支持推送（Push API）' }
  }
  if (!('Notification' in window)) {
    return { supported: false, reason: '当前浏览器不支持通知' }
  }
  return { supported: true, reason: '' }
}

/** 注册通知用 Service Worker；失败时返回 null，不阻断页面 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!pushCapability().supported) return null
  try {
    const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
    await navigator.serviceWorker.ready
    return registration
  } catch {
    return null
  }
}

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const output = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}

export function fetchPushConfig(): Promise<PushConfig> {
  return api<PushConfig>('/api/notifications/push/config')
}

export function fetchPushStatus(): Promise<PushStatus> {
  return api<PushStatus>('/api/notifications/push/status')
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (!('serviceWorker' in navigator)) return null
  const registration = (await navigator.serviceWorker.getRegistration('/')) ??
    (await navigator.serviceWorker.getRegistration())
  if (!registration) return null
  return registration.pushManager.getSubscription()
}

export async function enablePush(): Promise<PushStatus> {
  const capability = pushCapability()
  if (!capability.supported) throw new Error(capability.reason)

  const config = await fetchPushConfig()
  if (!config.enabled) throw new Error(config.reason || '服务端未启用手机通知')

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    throw new Error(
      permission === 'denied'
        ? '通知权限已被拒绝，请在浏览器或系统设置中允许本网站发送通知'
        : '未获得通知权限，请重试并点击「允许」',
    )
  }

  const registration = await registerServiceWorker()
  if (!registration) throw new Error('通知服务注册失败，请刷新页面后重试')

  let subscription = await registration.pushManager.getSubscription()
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(config.public_key),
    })
  }

  const payload = subscription.toJSON()
  const keys = payload.keys
  if (!payload.endpoint || !keys?.p256dh || !keys?.auth) {
    throw new Error('设备订阅信息不完整，请重试')
  }
  await api('/api/notifications/push/subscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: payload.endpoint,
      keys: { p256dh: keys.p256dh, auth: keys.auth },
      user_agent: navigator.userAgent.slice(0, 300),
    }),
  })
  localStorage.setItem(PUSH_ENDPOINT_KEY, payload.endpoint)
  return fetchPushStatus()
}

export async function disablePush(): Promise<PushStatus> {
  const subscription = await getCurrentSubscription()
  // 浏览器订阅可能已被系统清理，此时用本地保存的地址兜底删除服务端记录
  const endpoint = subscription?.endpoint ?? localStorage.getItem(PUSH_ENDPOINT_KEY)
  if (endpoint) {
    try {
      await api('/api/notifications/push/unsubscribe', {
        method: 'POST',
        body: JSON.stringify({ endpoint }),
      })
    } catch {
      /* 服务端记录可能已清理，继续取消浏览器订阅 */
    }
  }
  if (subscription) {
    try {
      await subscription.unsubscribe()
    } catch {
      /* 忽略浏览器取消失败 */
    }
  }
  localStorage.removeItem(PUSH_ENDPOINT_KEY)
  return fetchPushStatus()
}

export function sendTestPush(): Promise<PushTestResult> {
  return api<PushTestResult>('/api/notifications/push/test', { method: 'POST' })
}
