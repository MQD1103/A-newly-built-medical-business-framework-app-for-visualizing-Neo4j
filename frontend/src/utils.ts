import { apiUrl } from './api'

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/** 图片/上传资源地址（配合团队填写的 VITE_API_BASE） */
export function mediaUrl(path?: string | null): string {
  if (!path) return ''
  return apiUrl(path)
}

export function weekdayLabel(n: number): string {
  return WEEKDAYS[n] ?? String(n)
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(iso: string): string {
  const d = new Date(iso.includes('T') ? iso : `${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

/** 本机今天的 YYYY-MM-DD（给日期输入框的 max / 默认值用） */
export function todayISO(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 相对今天偏移 n 天的 YYYY-MM-DD */
export function offsetISO(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 距某日期还有几天；负数表示已过去 */
export function daysUntil(iso: string): number {
  const target = new Date(iso.includes('T') ? iso : `${iso}T00:00:00`).getTime()
  if (!Number.isFinite(target)) return 0
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target - today.getTime()) / 86_400_000)
}

export function roleLabel(role: string): string {
  if (role === 'student') return '用户'
  if (role === 'teacher') return '用户'
  if (role === 'admin') return '管理员'
  return role
}

export function audienceLabel(a: string): string {
  if (a === 'all') return '全体'
  if (a === 'student') return '用户'
  if (a === 'teacher') return '管理'
  return a
}

export const FREE_LABEL = '免费'

/** 价格文案（元）。价格缺失时退回该域内的默认价 */
export function formatPrice(n: number | undefined, fallback: number): string {
  const v = Number.isFinite(n) ? Number(n) : fallback
  return `¥${v.toFixed(2)}`
}

/**
 * 价格位文案：管理员全部功能免费开放，一律显示「免费」，
 * 其他角色照常显示金额。
 */
export function priceText(n: number | undefined, isAdmin: boolean, fallback: number): string {
  return isAdmin ? FREE_LABEL : formatPrice(n, fallback)
}

/**
 * 加好友按钮文案。返回 null 表示不渲染按钮（自己 / 已是好友）。
 * hasActed 用于刚点过之后的文案，避免重复提交。
 */
export function friendActionLabel(state: string, hasActed: boolean): string | null {
  if (state === 'self' || state === 'friends') return null
  if (state === 'pending_in') return hasActed ? '已同意' : '同意'
  if (state === 'pending_out') return hasActed ? '已发送申请' : '待验证'
  return hasActed ? '已发送申请' : '加好友'
}

/** 源码仓库地址：页面上的「GitHub 仓库」入口统一引用这里，改地址只改一处 */
export const REPO_URL =
  'https://github.com/MQD1103/A-newly-built-medical-business-framework-app-for-visualizing-Neo4j'
