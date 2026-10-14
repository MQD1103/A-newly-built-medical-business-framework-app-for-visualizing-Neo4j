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
