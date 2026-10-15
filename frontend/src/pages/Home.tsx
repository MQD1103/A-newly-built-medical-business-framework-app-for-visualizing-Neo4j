import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { CalendarEvent, HomeData, Notice, Reminder, ScheduleSlot } from '../types'
import { formatDate, formatDateTime, weekdayLabel } from '../utils'

type CommunityPostBrief = {
  id: number
  author_name: string
  content: string
  image_urls: string[]
  created_at: string
}

type NodeTone = 'center' | 'a' | 'b' | 'c'

type NodeDef = {
  id: string
  label: string
  sub?: string
  x: number
  y: number
  to?: string
  tone: NodeTone
}

type EdgeDef = { from: string; to: string }
type NodeMeta = Omit<NodeDef, 'x' | 'y'>

/** 全量节点目录（各层共用） */
const NODE_CATALOG: Record<string, NodeMeta> = {
  me: { id: 'me', label: '我', sub: '当前用户', to: '/me', tone: 'center' },
  schedule: { id: 'schedule', label: '服务', sub: '课表等服务', to: '/services', tone: 'a' },
  remind: { id: 'remind', label: '提醒', sub: '服务内提醒', to: '/reminders', tone: 'b' },
  notice: { id: 'notice', label: '公告', sub: '平台通知', to: '/notices', tone: 'c' },
  course: { id: 'course', label: '商城', sub: '课程与监督', to: '/mall', tone: 'a' },
  calendar: { id: 'calendar', label: '校历', sub: '重要节点', to: '/schedule', tone: 'b' },
  community: { id: 'community', label: '社区', sub: '小医动态', to: '/community', tone: 'c' },
  // 课表下层：教室并入「今日安排」卡片，不再单独成球
  today: { id: 'today', label: '今日安排', sub: '最多5堂课', to: '/schedule', tone: 'a' },
  week: { id: 'week', label: '本周', sub: '周一至周五', to: '/schedule', tone: 'b' },
  // 提醒下层
  due: { id: 'due', label: '临期', sub: '即将截止', to: '/reminders', tone: 'a' },
  online: { id: 'online', label: '网课', sub: '线上待办', to: '/reminders', tone: 'b' },
  // 公告下层
  school: { id: 'school', label: '校级', sub: '学校通知', to: '/notices', tone: 'a' },
  urgent: { id: 'urgent', label: '紧急', sub: '重要公告', to: '/notices', tone: 'c' },
  // 社区下层
  feed: { id: 'feed', label: '最新', sub: '最近动态', to: '/community', tone: 'a' },
  pics: { id: 'pics', label: '有图', sub: '带照片的', to: '/community', tone: 'b' },
  // 课程下层：负责人信息放进卡片，不占独立球
  materials: { id: 'materials', label: '资料', sub: '课件讲义', to: '/materials', tone: 'a' },
  score: { id: 'score', label: '成绩', sub: '考核结果', to: '/scores', tone: 'c' },
  // 校历下层
  exam: { id: 'exam', label: '考试', sub: '考试周', to: '/schedule', tone: 'a' },
  holiday: { id: 'holiday', label: '假期', sub: '放假安排', to: '/schedule', tone: 'b' },
}

/**
 * 静态层：
 * 第1层「我」→ 课表/提醒/…；
 * 第2层各模块入口；
 * 第3层动态球（同一套搜寻→隐其它→浮出，每层最多 5 球）。
 */
const LAYER_CHILDREN: Record<string, string[]> = {
  me: ['schedule', 'remind', 'notice', 'course', 'community'],
  schedule: ['today', 'week'],
  remind: ['due', 'online'],
  notice: ['school', 'urgent'],
  community: ['feed', 'pics'],
  course: ['materials', 'score'],
  calendar: ['exam', 'holiday'],
}

/** 可进入第三层的第二层节点 */
const DRILL_TO_L3 = new Set([
  'today',
  'week',
  'due',
  'online',
  'school',
  'urgent',
  'feed',
  'pics',
  'exam',
  'holiday',
])

/** 动态子层，由运行时写入 */
const dynamicChildren: Record<string, string[]> = {}
const dynamicMeta: Record<string, NodeMeta> = {}
const slotByNodeId: Record<string, ScheduleSlot> = {}
const daySlotsByNodeId: Record<string, ScheduleSlot[]> = {}
const remByNodeId: Record<string, Reminder> = {}
const noticeByNodeId: Record<string, Notice> = {}
const eventByNodeId: Record<string, CalendarEvent> = {}
const postByNodeId: Record<string, CommunityPostBrief> = {}

/** 第二层叶子：资料 / 成绩进详情卡再跳转完整页 */
type LeafCardKind = 'link'

const LEAF_CARDS: Record<
  string,
  { kind: LeafCardKind; title: string; blurb?: string; to?: string }
> = {
  materials: { kind: 'link', title: '课程资料', blurb: '课件链接与说明', to: '/materials' },
  score: { kind: 'link', title: '成绩', blurb: '考核成绩查询与录入', to: '/scores' },
}

const ROOT_ID = 'me'
const MAX_LAYER_DEPTH = 3
/** 第三层球体上限（一天最多五堂课 / 列表预览最多 5） */
const MAX_L3_BALLS = 5
const MAX_TODAY_SLOTS = MAX_L3_BALLS
const WEEK_WORKDAYS = 5
const SLOT_PREFIX = 'slot-'
const DAY_PREFIX = 'day-'
const REM_PREFIX = 'rem-'
/** 第一层浮动提醒球（不连主键、不连其它子键） */
const FLOAT_REM_PREFIX = 'frem-'
const NOTICE_PREFIX = 'ntc-'
const EVENT_PREFIX = 'evt-'
const POST_PREFIX = 'post-'
const CLICK_DRAG_THRESHOLD = 8
const SLOT_TONES: NodeTone[] = ['a', 'b', 'c', 'a', 'b']

type RemUrgency = 'ok' | 'warn' | 'urgent' | 'critical' | 'gone'

function reminderUrgency(dueAt: string, now: number): RemUrgency {
  const left = new Date(dueAt).getTime() - now
  if (!Number.isFinite(left) || left <= 0) return 'gone'
  const h = left / 3_600_000
  if (h <= 6) return 'critical'
  if (h <= 24) return 'urgent'
  if (h <= 72) return 'warn'
  return 'ok'
}

function formatCountdown(dueAt: string, now: number): string {
  const left = new Date(dueAt).getTime() - now
  if (!Number.isFinite(left) || left <= 0) return '已结束'
  const totalMin = Math.floor(left / 60_000)
  const d = Math.floor(totalMin / (60 * 24))
  const h = Math.floor((totalMin % (60 * 24)) / 60)
  const m = totalMin % 60
  if (d > 0) return `${d}天${h}时`
  if (h > 0) return `${h}时${m}分`
  return `${Math.max(1, m)}分`
}

/** 剩余时间占比（7 天窗），用于卡片进度条 */
function remainRatio(dueAt: string, now: number, windowMs = 7 * 86_400_000): number {
  const left = new Date(dueAt).getTime() - now
  if (!Number.isFinite(left) || left <= 0) return 0
  return Math.max(0, Math.min(1, left / windowMs))
}

function activeFloatReminders(list: Reminder[], now: number): Reminder[] {
  return list
    .filter((r) => r.notify_enabled !== false)
    .filter((r) => reminderUrgency(r.due_at, now) !== 'gone')
    .sort((a, b) => a.due_at.localeCompare(b.due_at))
    .slice(0, MAX_L3_BALLS)
}

function isSlotNodeId(id: string): boolean {
  return id.startsWith(SLOT_PREFIX)
}

function isDayNodeId(id: string): boolean {
  return id.startsWith(DAY_PREFIX)
}

function isFloatRemNodeId(id: string): boolean {
  return id.startsWith(FLOAT_REM_PREFIX)
}

function isRemNodeId(id: string): boolean {
  return id.startsWith(REM_PREFIX) || isFloatRemNodeId(id)
}

function isNoticeNodeId(id: string): boolean {
  return id.startsWith(NOTICE_PREFIX)
}

function isEventNodeId(id: string): boolean {
  return id.startsWith(EVENT_PREFIX)
}

function isPostNodeId(id: string): boolean {
  return id.startsWith(POST_PREFIX)
}

function isL3LeafId(id: string): boolean {
  return (
    isSlotNodeId(id) ||
    isDayNodeId(id) ||
    isRemNodeId(id) ||
    isNoticeNodeId(id) ||
    isEventNodeId(id) ||
    isPostNodeId(id)
  )
}

function slotNodeId(slotId: number): string {
  return `${SLOT_PREFIX}${slotId}`
}

function dayNodeId(weekday: number): string {
  return `${DAY_PREFIX}${weekday}`
}

function shortCourseLabel(name: string, max = 3): string {
  const t = name.trim()
  return t.length <= max ? t : t.slice(0, max)
}

function clearDynamicGroup(prefix: string, store: Record<string, object | ScheduleSlot | ScheduleSlot[]>) {
  for (const key of Object.keys(store)) {
    if (key.startsWith(prefix)) {
      delete store[key]
      delete dynamicMeta[key]
    }
  }
}

function getChildren(primaryId: string): string[] {
  return dynamicChildren[primaryId] ?? LAYER_CHILDREN[primaryId] ?? []
}

/** 当前路径深度未满且目标有下层时，才允许升为主键 */
function canDrillFrom(pathLen: number, nodeId: string): boolean {
  if (pathLen >= MAX_LAYER_DEPTH) return false
  if (DRILL_TO_L3.has(nodeId)) return true
  return getChildren(nodeId).length > 0
}

function edgesFor(primaryId: string): EdgeDef[] {
  return getChildren(primaryId).map((to) => ({ from: primaryId, to }))
}

function metaOf(id: string, userName?: string): NodeMeta {
  if (dynamicMeta[id]) return dynamicMeta[id]
  const base = NODE_CATALOG[id] ?? {
    id,
    label: id,
    sub: '',
    tone: 'a' as NodeTone,
  }
  if (id === ROOT_ID && userName) {
    return {
      ...base,
      label: userName.slice(0, 1) || '我',
      sub: userName,
    }
  }
  return base
}

/** 按今日课表写入第三层子球（最多 5） */
function applyTodaySlotChildren(slots: ScheduleSlot[]) {
  clearDynamicGroup(SLOT_PREFIX, slotByNodeId)

  const sorted = [...slots]
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
    .slice(0, MAX_TODAY_SLOTS)

  const ids: string[] = []
  sorted.forEach((s, i) => {
    const nid = slotNodeId(s.id)
    ids.push(nid)
    slotByNodeId[nid] = s
    dynamicMeta[nid] = {
      id: nid,
      label: shortCourseLabel(s.course_name),
      sub: s.start_time,
      to: '/schedule',
      tone: SLOT_TONES[i % SLOT_TONES.length],
    }
  })
  dynamicChildren.today = ids
}

/** 本周第三层：周一…周五共 5 球（每天课次进卡片，一天最多展示 5 节） */
function applyWeekDayChildren(slots: ScheduleSlot[]) {
  clearDynamicGroup(DAY_PREFIX, daySlotsByNodeId)

  const ids: string[] = []
  for (let d = 0; d < WEEK_WORKDAYS; d++) {
    const nid = dayNodeId(d)
    ids.push(nid)
    const items = slots
      .filter((s) => s.weekday === d)
      .slice()
      .sort((a, b) => a.start_time.localeCompare(b.start_time))
      .slice(0, MAX_TODAY_SLOTS)
    daySlotsByNodeId[nid] = items
    const short = weekdayLabel(d).replace(/^周/, '')
    dynamicMeta[nid] = {
      id: nid,
      label: short,
      sub: items.length ? `${items.length}节` : '无课',
      to: '/schedule',
      tone: SLOT_TONES[d % SLOT_TONES.length],
    }
  }
  dynamicChildren.week = ids
}

/** 提醒第三层：临期 / 网课，各最多 5 球 */
function applyRemindChildren(parentId: 'due' | 'online', list: Reminder[]) {
  const oldIds = dynamicChildren[parentId] ?? []
  for (const id of oldIds) {
    delete remByNodeId[id]
    delete dynamicMeta[id]
  }

  let filtered =
    parentId === 'online'
      ? list.filter((r) => !!(r.external_url && r.external_url.trim()))
      : [...list].sort((a, b) => a.due_at.localeCompare(b.due_at))

  filtered = filtered.slice(0, MAX_L3_BALLS)
  const ids: string[] = []
  filtered.forEach((r, i) => {
    const nid = `${REM_PREFIX}${parentId}-${r.id}`
    ids.push(nid)
    remByNodeId[nid] = r
    dynamicMeta[nid] = {
      id: nid,
      label: shortCourseLabel(r.title),
      sub: r.status === 'overdue' ? '逾期' : shortCourseLabel(r.course_name, 4),
      to: '/reminders',
      tone: SLOT_TONES[i % SLOT_TONES.length],
    }
  })
  dynamicChildren[parentId] = ids
}

/** 公告第三层：校级 / 紧急，各最多 5 球 */
function applyNoticeChildren(parentId: 'school' | 'urgent', list: Notice[]) {
  const oldIds = dynamicChildren[parentId] ?? []
  for (const id of oldIds) {
    delete noticeByNodeId[id]
    delete dynamicMeta[id]
  }

  let filtered =
    parentId === 'urgent'
      ? list.filter((n) => !!n.is_urgent)
      : list.filter((n) => !n.is_urgent)
  // 校级：优先非紧急；若空则回退全部非紧急已在上面；紧急无数据则空球
  if (parentId === 'school' && !filtered.length) {
    filtered = list.filter((n) => n.audience === 'all' || n.audience === 'student')
  }
  filtered = filtered.slice(0, MAX_L3_BALLS)

  const ids: string[] = []
  filtered.forEach((n, i) => {
    const nid = `${NOTICE_PREFIX}${parentId}-${n.id}`
    ids.push(nid)
    noticeByNodeId[nid] = n
    dynamicMeta[nid] = {
      id: nid,
      label: shortCourseLabel(n.title),
      sub: n.is_urgent
        ? '紧急'
        : n.audience === 'teacher'
          ? '管理'
          : n.audience === 'student'
            ? '用户'
            : '全部',
      to: `/notices/${n.id}`,
      tone: parentId === 'urgent' ? 'c' : SLOT_TONES[i % SLOT_TONES.length],
    }
  })
  dynamicChildren[parentId] = ids
}

/** 校历第三层：考试 / 假期，各最多 5 球 */
function applyEventChildren(parentId: 'exam' | 'holiday', list: CalendarEvent[]) {
  const oldIds = dynamicChildren[parentId] ?? []
  for (const id of oldIds) {
    delete eventByNodeId[id]
    delete dynamicMeta[id]
  }

  const keyword = parentId === 'exam' ? /考/ : /假|休|节/
  let filtered = list.filter((e) => keyword.test(e.title) || keyword.test(e.description || ''))
  if (!filtered.length) filtered = [...list]
  filtered = filtered.slice(0, MAX_L3_BALLS)

  const ids: string[] = []
  filtered.forEach((e, i) => {
    const nid = `${EVENT_PREFIX}${parentId}-${e.id}`
    ids.push(nid)
    eventByNodeId[nid] = e
    dynamicMeta[nid] = {
      id: nid,
      label: shortCourseLabel(e.title),
      sub: formatDate(e.event_date),
      to: '/schedule',
      tone: SLOT_TONES[i % SLOT_TONES.length],
    }
  })
  dynamicChildren[parentId] = ids
}

/** 社区第三层：最新 / 有图，各最多 5 球 */
function applyCommunityChildren(parentId: 'feed' | 'pics', list: CommunityPostBrief[]) {
  const oldIds = dynamicChildren[parentId] ?? []
  for (const id of oldIds) {
    delete postByNodeId[id]
    delete dynamicMeta[id]
  }

  let filtered =
    parentId === 'pics'
      ? list.filter((p) => (p.image_urls?.length ?? 0) > 0)
      : [...list]
  if (!filtered.length && parentId === 'pics') filtered = [...list]
  filtered = filtered.slice(0, MAX_L3_BALLS)

  const ids: string[] = []
  filtered.forEach((p, i) => {
    const nid = `${POST_PREFIX}${parentId}-${p.id}`
    ids.push(nid)
    postByNodeId[nid] = p
    const preview = (p.content || '').trim() || (p.image_urls?.length ? '照片动态' : '动态')
    dynamicMeta[nid] = {
      id: nid,
      label: shortCourseLabel(preview),
      sub: shortCourseLabel(p.author_name || '用户', 4),
      to: '/community',
      tone: SLOT_TONES[i % SLOT_TONES.length],
    }
  })
  dynamicChildren[parentId] = ids
}

/** 球视觉半径（宽 68px） */
const NODE_RADIUS = 34
/** 两球中心最小间距（直径 + 空隙，保证默认不重合） */
const NODE_KEEP_DIST = NODE_RADIUS * 2 + 28 // 96

/** 全员互斥分离，可选钉住主键 */
function separateAll(
  list: NodeDef[],
  keepDist: number,
  fixedId: string | null,
): NodeDef[] {
  const pos = new Map(list.map((n) => [n.id, { x: n.x, y: n.y }]))
  for (let iter = 0; iter < 16; iter++) {
    const ids = [...pos.keys()]
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = pos.get(ids[i])!
        const b = pos.get(ids[j])!
        let dx = b.x - a.x
        let dy = b.y - a.y
        let dist = Math.hypot(dx, dy)
        if (dist >= keepDist) continue
        if (dist < 0.001) {
          dx = 1
          dy = 0
          dist = 0.001
        }
        const push = (keepDist - dist) / dist
        const aFixed = ids[i] === fixedId
        const bFixed = ids[j] === fixedId
        if (aFixed && !bFixed) {
          b.x += dx * push
          b.y += dy * push
        } else if (bFixed && !aFixed) {
          a.x -= dx * push
          a.y -= dy * push
        } else if (!aFixed && !bFixed) {
          a.x -= dx * push * 0.5
          a.y -= dy * push * 0.5
          b.x += dx * push * 0.5
          b.y += dy * push * 0.5
        }
      }
    }
  }
  return list.map((n) => {
    const p = pos.get(n.id)!
    return { ...n, x: p.x, y: p.y }
  })
}

/**
 * 第一层浮动提醒球：出现在画布左侧，不写入 edges（不连主键、不连其它子键）。
 * 可保留已有坐标，避免倒计时刷新时跳动。
 */
function placeFloatingReminders(
  base: NodeDef[],
  w: number,
  h: number,
  reminders: Reminder[],
  now: number,
  keepPos?: Map<string, { x: number; y: number }>,
): NodeDef[] {
  for (const key of Object.keys(remByNodeId)) {
    if (key.startsWith(FLOAT_REM_PREFIX)) {
      delete remByNodeId[key]
      delete dynamicMeta[key]
    }
  }

  const active = activeFloatReminders(reminders, now)
  if (!active.length) {
    return base.filter((n) => !isFloatRemNodeId(n.id))
  }

  const core = base.filter((n) => !isFloatRemNodeId(n.id))
  const floats: NodeDef[] = active.map((r, i) => {
    const nid = `${FLOAT_REM_PREFIX}${r.id}`
    remByNodeId[nid] = r
    const n = active.length
    const t = n === 1 ? 0.5 : i / (n - 1)
    const fallback = { x: w * 0.14, y: h * (0.22 + t * 0.56) }
    const pos = keepPos?.get(nid) ?? fallback
    const meta: NodeMeta = {
      id: nid,
      label: shortCourseLabel(r.title),
      sub: formatCountdown(r.due_at, now),
      to: '/reminders',
      tone: 'c',
    }
    dynamicMeta[nid] = meta
    return { ...meta, x: pos.x, y: pos.y }
  })

  return separateAll([...core, ...floats], NODE_KEEP_DIST, core.find((n) => n.id === ROOT_ID)?.id ?? null)
}

type LayoutOpts = {
  floatReminders?: Reminder[]
  now?: number
  keepFloatPos?: Map<string, { x: number; y: number }>
}

/**
 * 当前层布局：主键居中，子节点均匀环绕且互不重合（默认 / 复位 / 切层共用）
 * 第一层可附加无连线浮动提醒球。
 */
function layoutLayer(
  w: number,
  h: number,
  primaryId: string,
  userName: string,
  opts?: LayoutOpts,
): NodeDef[] {
  const width = Math.max(w, 280)
  const height = Math.max(h, 360)
  const cx = width * 0.5
  const cy = height * 0.5
  const childIds = getChildren(primaryId)
  const count = childIds.length

  const pad = NODE_RADIUS + 22
  const maxR = Math.max(NODE_KEEP_DIST, Math.min(cx, cy) - pad)
  // 0/1 个子键时不按弦长公式，避免 sin(π)=0 → Infinity
  const minRByChord =
    count < 2 ? NODE_KEEP_DIST : NODE_KEEP_DIST / (2 * Math.sin(Math.PI / count))
  const minR = Math.max(NODE_KEEP_DIST * 1.08, minRByChord)
  // 舒适环半径：保证疏朗，并与防重合下限、画布上限夹紧
  const preferred = Math.min(width, height) * 0.36
  const r = Math.max(minR, Math.min(maxR, preferred))

  const primaryMeta = metaOf(primaryId, userName)
  const laid: NodeDef[] = [
    { ...primaryMeta, tone: 'center', x: cx, y: cy },
  ]

  if (count > 0) {
    childIds.forEach((id, idx) => {
      const ang = -Math.PI / 2 + (idx * 2 * Math.PI) / count
      const meta = metaOf(id, userName)
      laid.push({
        ...meta,
        tone: meta.tone === 'center' ? 'a' : meta.tone,
        x: cx + Math.cos(ang) * r,
        y: cy + Math.sin(ang) * r,
      })
    })
  }

  const ring = separateAll(laid, NODE_KEEP_DIST, primaryId)
  if (primaryId === ROOT_ID && opts?.floatReminders?.length) {
    return placeFloatingReminders(
      ring,
      width,
      height,
      opts.floatReminders,
      opts.now ?? Date.now(),
      opts.keepFloatPos,
    )
  }
  return ring
}

type PushResult = { list: NodeDef[]; bumped: string[] }

/**
 * 仅处理与手中球的碰撞：手中球钉住不动，
 * 只有被碰到的球被挤开；其它未碰撞的球完全不动。
 */
function resolveCollisionsWith(
  list: NodeDef[],
  moverId: string,
  keepDist: number,
): PushResult {
  const pos = new Map(list.map((n) => [n.id, { x: n.x, y: n.y }]))
  const mover = pos.get(moverId)
  const bumped = new Set<string>()
  if (!mover) return { list, bumped: [] }

  for (let iter = 0; iter < 6; iter++) {
    for (const [id, p] of pos) {
      if (id === moverId) continue
      let dx = p.x - mover.x
      let dy = p.y - mover.y
      let dist = Math.hypot(dx, dy)
      if (dist >= keepDist) continue
      if (dist < 0.001) {
        dx = 1
        dy = 0
        dist = 0.001
      }
      bumped.add(id)
      const s = keepDist / dist
      p.x = mover.x + dx * s
      p.y = mover.y + dy * s
    }
  }

  return {
    list: list.map((n) => {
      const p = pos.get(n.id)!
      return { ...n, x: p.x, y: p.y }
    }),
    bumped: [...bumped],
  }
}

export default function Home() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const navigate = useNavigate()
  const stageRef = useRef<HTMLDivElement>(null)
  const nodesRef = useRef<NodeDef[]>([])
  const targetsRef = useRef<NodeDef[]>([])
  const sizeRef = useRef({ w: 360, h: 520 })
  const panRef = useRef({ x: 0, y: 0 })
  const dragIdRef = useRef<string | null>(null)
  const dragGrabRef = useRef({ x: 0, y: 0 })
  const dragPointerRef = useRef<number | null>(null)
  const pointerStartRef = useRef({ x: 0, y: 0 })
  const didDragRef = useRef(false)
  const primaryIdRef = useRef(ROOT_ID)
  const pathRef = useRef<string[]>([ROOT_ID])
  const panningRef = useRef(false)
  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 })
  const rafRef = useRef<number | null>(null)
  const paintScheduled = useRef(false)
  const [canvasPanning, setCanvasPanning] = useState(false)

  const [primaryId, setPrimaryId] = useState(ROOT_ID)
  const [path, setPath] = useState<string[]>([ROOT_ID])
  const [size, setSize] = useState({ w: 360, h: 520 })
  const [nodes, setNodes] = useState<NodeDef[]>(() =>
    layoutLayer(360, 520, ROOT_ID, user?.full_name || '我'),
  )
  const [dragId, setDragId] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(ROOT_ID)
  const [sideOpen, setSideOpen] = useState(false)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [panAnim, setPanAnim] = useState(true)
  const [locateId, setLocateId] = useState<string | null>(null)
  const [seeking, setSeeking] = useState(false)
  const [seekLabel, setSeekLabel] = useState('')
  const locateTimer = useRef<number | null>(null)
  const seekTimer = useRef<number | null>(null)
  const bumpTimer = useRef<number | null>(null)
  const enterTimer = useRef<number | null>(null)
  const transitioningRef = useRef(false)
  const [bumpedIds, setBumpedIds] = useState<string[]>([])
  const [dimmedIds, setDimmedIds] = useState<string[]>([])
  const [enteringIds, setEnteringIds] = useState<string[]>([])
  const [sinkingIds, setSinkingIds] = useState<string[]>([])
  const [edgesReady, setEdgesReady] = useState(true)
  const [edgeAnimKey, setEdgeAnimKey] = useState(0)
  const [seekFocusId, setSeekFocusId] = useState<string | null>(null)
  const [primarySettle, setPrimarySettle] = useState(false)
  const [infoCardId, setInfoCardId] = useState<string | null>(null)
  /** 第一层浮动提醒（未到期）；到期后先消散再移除 */
  const [floatReminders, setFloatReminders] = useState<Reminder[]>([])
  const [vanishingRemIds, setVanishingRemIds] = useState<string[]>([])
  const [nowTick, setNowTick] = useState(() => Date.now())
  const homeCache = useRef<HomeData | null>(null)
  const weekCache = useRef<ScheduleSlot[] | null>(null)
  const remindCache = useRef<Reminder[] | null>(null)
  const noticeCache = useRef<Notice[] | null>(null)
  const eventCache = useRef<CalendarEvent[] | null>(null)
  const communityCache = useRef<CommunityPostBrief[] | null>(null)
  const floatRemRef = useRef<Reminder[]>([])
  const nowTickRef = useRef(nowTick)
  const vanishTimer = useRef<number | null>(null)

  primaryIdRef.current = primaryId
  pathRef.current = path
  floatRemRef.current = floatReminders
  nowTickRef.current = nowTick
  // 拖拽期间不要用旧 state 覆盖 ref
  panRef.current = pan
  if (!dragIdRef.current) {
    nodesRef.current = nodes
  }

  /** 星形连线只含模块子键，不含浮动提醒球 */
  const layerEdges = useMemo(() => edgesFor(primaryId), [primaryId])

  function layoutOptsFor(primary: string, keepFloatPos?: Map<string, { x: number; y: number }>): LayoutOpts | undefined {
    if (primary !== ROOT_ID) return undefined
    return {
      floatReminders: floatRemRef.current,
      now: nowTickRef.current,
      keepFloatPos,
    }
  }
  const primaryLabel =
    nodes.find((n) => n.id === primaryId)?.label ||
    NODE_CATALOG[primaryId]?.label ||
    '关系'
  const layerDepth = path.length
  const dimmedSet = useMemo(() => new Set(dimmedIds), [dimmedIds])
  const enteringSet = useMemo(() => new Set(enteringIds), [enteringIds])
  const sinkingSet = useMemo(() => new Set(sinkingIds), [sinkingIds])

  function schedulePaint() {
    if (paintScheduled.current) return
    paintScheduled.current = true
    requestAnimationFrame(() => {
      paintScheduled.current = false
      const safe = nodesRef.current.map((n) => ({
        ...n,
        x: Number.isFinite(n.x) ? n.x : 0,
        y: Number.isFinite(n.y) ? n.y : 0,
      }))
      nodesRef.current = safe
      setNodes(safe)
    })
  }

  // 被挤开的球柔和跟进；手中球由指针直接写坐标，不走插值
  useEffect(() => {
    if (!targetsRef.current.length) {
      targetsRef.current = nodesRef.current.map((n) => ({ ...n }))
    }

    const tick = () => {
      const targets = targetsRef.current
      const current = nodesRef.current
      const dragging = dragIdRef.current
      let changed = false

      const next = current.map((n) => {
        const t = targets.find((x) => x.id === n.id) ?? n
        if (dragging === n.id) {
          // 拖拽中坐标已在 pointermove 里写好，这里只同步 label
          return { ...n, label: t.label, sub: t.sub }
        }
        const alpha = dragging ? 0.35 : 0.18
        const nx = n.x + (t.x - n.x) * alpha
        const ny = n.y + (t.y - n.y) * alpha
        if (Math.abs(nx - n.x) > 0.05 || Math.abs(ny - n.y) > 0.05) changed = true
        return { ...n, x: nx, y: ny, label: t.label, sub: t.sub }
      })

      if (changed) {
        nodesRef.current = next
        schedulePaint()
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  function flashBumped(ids: string[]) {
    if (!ids.length) return
    setBumpedIds(ids)
    if (bumpTimer.current) window.clearTimeout(bumpTimer.current)
    bumpTimer.current = window.setTimeout(() => setBumpedIds([]), 280)
  }

  useEffect(() => {
    const el = stageRef.current
    if (!el) return

    const applySize = (width: number, height: number, resetLayout: boolean) => {
      sizeRef.current = { w: width, h: height }
      setSize({ w: width, h: height })

      const keep = new Map(
        nodesRef.current
          .filter((n) => isFloatRemNodeId(n.id))
          .map((n) => [n.id, { x: n.x, y: n.y }]),
      )
      const laid = layoutLayer(
        width,
        height,
        primaryIdRef.current,
        user?.full_name || '我',
        layoutOptsFor(primaryIdRef.current, keep),
      )
      targetsRef.current = laid
      nodesRef.current = laid
      setNodes(laid)
      if (resetLayout) setEdgesReady(true)
    }

    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width < 10 || height < 10) return
      applySize(width, height, false)
    })
    ro.observe(el)
    applySize(el.clientWidth, el.clientHeight, true)
    return () => ro.disconnect()
  }, [user?.full_name])

  async function refreshFloatReminders() {
    try {
      const list = await api<Reminder[]>('/api/reminders')
      remindCache.current = list
      const now = Date.now()
      nowTickRef.current = now
      setNowTick(now)
      setFloatReminders(activeFloatReminders(list, now))
      setVanishingRemIds([])
    } catch {
      setFloatReminders([])
    }
  }

  // 首次拉取第一层浮动提醒
  useEffect(() => {
    void refreshFloatReminders()
  }, [])

  // 倒计时心跳：开卡或临近截止时 1s，否则 15s
  useEffect(() => {
    const remOpen = !!(infoCardId && isRemNodeId(infoCardId))
    const hasCritical = floatReminders.some(
      (r) => reminderUrgency(r.due_at, Date.now()) === 'critical',
    )
    const ms = remOpen || hasCritical ? 1000 : 15_000
    const t = window.setInterval(() => setNowTick(Date.now()), ms)
    return () => window.clearInterval(t)
  }, [infoCardId, floatReminders])

  // 同步浮球：变色 / 到期先消散再移除
  useEffect(() => {
    const alive = activeFloatReminders(floatReminders, nowTick)
    const gone = floatReminders.filter((r) => !alive.some((a) => a.id === r.id))

    if (gone.length && vanishingRemIds.length === 0) {
      const ids = gone.map((r) => `${FLOAT_REM_PREFIX}${r.id}`)
      setVanishingRemIds(ids)
      if (vanishTimer.current) window.clearTimeout(vanishTimer.current)
      vanishTimer.current = window.setTimeout(() => {
        setFloatReminders(alive)
        setVanishingRemIds([])
        if (infoCardId && ids.includes(infoCardId)) setInfoCardId(null)
        vanishTimer.current = null
      }, 520)
      return
    }

    if (primaryIdRef.current !== ROOT_ID || transitioningRef.current) return
    if (dragIdRef.current) return

    const keep = new Map(
      nodesRef.current
        .filter((n) => isFloatRemNodeId(n.id))
        .map((n) => [n.id, { x: n.x, y: n.y }]),
    )
    const w = sizeRef.current.w
    const h = sizeRef.current.h
    const core = nodesRef.current.filter((n) => !isFloatRemNodeId(n.id))
    // 消散中的球暂时留在列表里播动画
    const showList =
      vanishingRemIds.length > 0
        ? floatReminders.filter(
            (r) =>
              alive.some((a) => a.id === r.id) ||
              vanishingRemIds.includes(`${FLOAT_REM_PREFIX}${r.id}`),
          )
        : alive
    const next = placeFloatingReminders(core, w, h, showList, nowTick, keep)
    targetsRef.current = next
    nodesRef.current = next
    setNodes(next)
  }, [nowTick, floatReminders, infoCardId, vanishingRemIds])

  const byId = useMemo(() => {
    const m = new Map<string, NodeDef>()
    nodes.forEach((n) => m.set(n.id, n))
    return m
  }, [nodes])

  /** 扩大 SVG 覆盖全部节点，避免 7cm 长边被裁切 */
  const worldBox = useMemo(() => {
    const fallback = { x: 0, y: 0, w: Math.max(1, size.w), h: Math.max(1, size.h) }
    if (!nodes.length) return fallback

    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    let valid = 0
    for (const n of nodes) {
      if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) continue
      valid += 1
      minX = Math.min(minX, n.x - 50)
      minY = Math.min(minY, n.y - 50)
      maxX = Math.max(maxX, n.x + 50)
      maxY = Math.max(maxY, n.y + 50)
    }
    if (!valid || !Number.isFinite(minX) || !Number.isFinite(minY)) return fallback

    const pad = 40
    minX -= pad
    minY -= pad
    maxX += pad
    maxY += pad
    const w = Math.max(fallback.w, maxX - minX)
    const h = Math.max(fallback.h, maxY - minY)
    if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return fallback
    return { x: minX, y: minY, w, h }
  }, [nodes, size.w, size.h])

  const selectedNode = selected ? byId.get(selected) : null

  function setTargets(next: NodeDef[]) {
    targetsRef.current = next
  }

  /**
   * 与「寻找节点」相同的特效：准星 + 背景网格 + 平移到中心。
   * hideOthers=true 时同时藏起其他键；全程同一画布背景，不换页。
   */
  function seekNodeToCenter(
    id: string,
    options?: { hideOthers?: boolean; label?: string; keepSeeking?: boolean },
  ): Promise<void> {
    return new Promise((resolve) => {
      const stage = stageRef.current
      const n =
        targetsRef.current.find((item) => item.id === id) ??
        nodesRef.current.find((item) => item.id === id)
      setSelected(id)
      if (!stage || !n) {
        resolve()
        return
      }

      if (options?.hideOthers) {
        setDimmedIds(nodesRef.current.filter((node) => node.id !== id).map((node) => node.id))
        setEdgesReady(false)
      }

      const w = stage.clientWidth
      const h = stage.clientHeight
      const cx = w * 0.5
      const cy = h * 0.5
      const screenX = n.x + panRef.current.x
      const screenY = n.y + panRef.current.y
      const nextPan = {
        x: panRef.current.x + (cx - screenX),
        y: panRef.current.y + (cy - screenY),
      }

      setSeekFocusId(id)
      setSeeking(true)
      setSeekLabel(options?.label || `正在定位 · ${n.label}`)
      setPanAnim(true)
      setPan(nextPan)
      panRef.current = nextPan

      if (locateTimer.current) window.clearTimeout(locateTimer.current)
      if (seekTimer.current) window.clearTimeout(seekTimer.current)

      seekTimer.current = window.setTimeout(() => {
        setPanAnim(false)
        // 只保留焦点球在画布上，其它键从同一背景移除（已淡出）
        const bakedAll = targetsRef.current.map((node) => ({
          ...node,
          x: node.x + nextPan.x,
          y: node.y + nextPan.y,
        }))
        const kept = options?.hideOthers
          ? bakedAll.filter((node) => node.id === id)
          : bakedAll
        setTargets(kept)
        nodesRef.current = kept
        setNodes(kept)
        setDimmedIds([])
        setPan({ x: 0, y: 0 })
        panRef.current = { x: 0, y: 0 }
        if (!options?.keepSeeking) {
          setSeeking(false)
          setSeekLabel('')
          setSeekFocusId(null)
        }
        setLocateId(id)
        requestAnimationFrame(() => setPanAnim(true))
        locateTimer.current = window.setTimeout(() => setLocateId(null), 850)
        resolve()
      }, 650)
    })
  }

  function focusNode(id: string) {
    setEdgesReady(true)
    void seekNodeToCenter(id)
  }

  function applyDragAt(clientX: number, clientY: number) {
    const id = dragIdRef.current
    const stage = stageRef.current
    if (!id || !stage) return

    const rect = stage.getBoundingClientRect()
    const x = clientX - rect.left - panRef.current.x - dragGrabRef.current.x
    const y = clientY - rect.top - panRef.current.y - dragGrabRef.current.y
    if (!Number.isFinite(x) || !Number.isFinite(y)) return

    let moved = targetsRef.current.map((n) => (n.id === id ? { ...n, x, y } : n))
    const pushed = resolveCollisionsWith(moved, id, NODE_KEEP_DIST)
    moved = pushed.list
    if (pushed.bumped.length) flashBumped(pushed.bumped)
    targetsRef.current = moved

    // 手中球立刻跟手写进 ref，下一帧刷到画面
    nodesRef.current = nodesRef.current.map((n) => {
      if (n.id !== id) return n
      const t = moved.find((m) => m.id === id)!
      return { ...n, x: t.x, y: t.y }
    })
    schedulePaint()
  }

  function endNodeDrag() {
    const id = dragIdRef.current
    if (id) {
      const next = resolveCollisionsWith(targetsRef.current, id, NODE_KEEP_DIST).list
      targetsRef.current = next
      nodesRef.current = nodesRef.current.map((n) => {
        const t = next.find((m) => m.id === n.id)
        return t ? { ...n, x: t.x, y: t.y } : n
      })
      schedulePaint()
    }
    dragIdRef.current = null
    dragPointerRef.current = null
    setDragId(null)
  }

  /**
   * 仍在同一层画布（不换页）：
   * 主键留在中心 → 子键与连线「浮出水面」。
   */
  function revealLayer(nextPrimary: string, nextPath: string[]) {
    const stage = stageRef.current
    const w = Math.max(stage?.clientWidth || 0, sizeRef.current.w, size.w, 320)
    const h = Math.max(stage?.clientHeight || 0, sizeRef.current.h, size.h, 400)
    sizeRef.current = { w, h }
    setSize({ w, h })

    const keep = new Map(
      nodesRef.current
        .filter((n) => isFloatRemNodeId(n.id))
        .map((n) => [n.id, { x: n.x, y: n.y }]),
    )
    const laid = layoutLayer(
      w,
      h,
      nextPrimary,
      user?.full_name || '我',
      layoutOptsFor(nextPrimary, keep),
    )
    const primaryFinal = laid.find((n) => n.id === nextPrimary)!
    // 浮出：模块子键；浮动提醒若在第一层则一并保留（仍无连线）
    const childNodes = laid.filter((n) => n.id !== nextPrimary)
    const childIds = childNodes.map((n) => n.id)

    // 承接搜寻结束后的中心球位置，避免闪切
    const existing = nodesRef.current.find((n) => n.id === nextPrimary)
    const inheritCenter = nodesRef.current.find((n) => n.id === primaryIdRef.current)
    const anchor = existing ?? inheritCenter
    const primaryNow: NodeDef = anchor
      ? { ...primaryFinal, x: anchor.x, y: anchor.y }
      : { ...primaryFinal }

    primaryIdRef.current = nextPrimary
    pathRef.current = nextPath
    setPrimaryId(nextPrimary)
    setPath(nextPath)
    setSelected(nextPrimary)
    setBumpedIds([])
    setDimmedIds([])
    setSinkingIds([])
    dragIdRef.current = null
    dragPointerRef.current = null
    setDragId(null)
    setPan({ x: 0, y: 0 })
    panRef.current = { x: 0, y: 0 }
    setEdgesReady(false)
    setPrimarySettle(true)
    setInfoCardId(null)

    // 先只留主键（其它子键已隐藏），仍是同一页面
    targetsRef.current = [{ ...primaryFinal }]
    nodesRef.current = [primaryNow]
    setNodes([primaryNow])
    setEnteringIds([])

    if (enterTimer.current) window.clearTimeout(enterTimer.current)

    // 子键在环上浮出水面 → 连线跟上
    enterTimer.current = window.setTimeout(() => {
      const next = [{ ...primaryFinal }, ...childNodes]
      targetsRef.current = laid
      nodesRef.current = next
      setNodes(next)
      setEnteringIds(childIds)

      setSeeking(false)
      setSeekLabel('')
      setSeekFocusId(null)

      window.setTimeout(() => {
        setEdgesReady(true)
        setEdgeAnimKey((k) => k + 1)
      }, 240)
      window.setTimeout(() => setPrimarySettle(false), 500)
      enterTimer.current = window.setTimeout(() => setEnteringIds([]), 860)
    }, 120)

    setLocateId(nextPrimary)
    if (locateTimer.current) window.clearTimeout(locateTimer.current)
    locateTimer.current = window.setTimeout(() => setLocateId(null), 700)
  }

  function wait(ms: number) {
    return new Promise<void>((r) => {
      window.setTimeout(r, ms)
    })
  }

  function closeInfoCard() {
    setInfoCardId(null)
  }

  async function ensureHomeSnap() {
    if (homeCache.current) return homeCache.current
    const data = await api<HomeData>('/api/home')
    homeCache.current = data
    return data
  }

  async function ensureWeekSlots() {
    if (weekCache.current) return weekCache.current
    const slots = await api<ScheduleSlot[]>('/api/schedule/slots')
    weekCache.current = slots
    return slots
  }

  async function openInfoCard(id: string) {
    // 第三层叶子球：详情卡，不再下钻
    if (isL3LeafId(id)) {
      setInfoCardId(id)
      setSelected(id)
      return
    }

    const meta = LEAF_CARDS[id]
    if (!meta) return
    setInfoCardId(id)
    setSelected(id)
  }

  async function ensureRemindList() {
    if (remindCache.current) return remindCache.current
    try {
      const data = await ensureHomeSnap()
      if (data.upcoming_reminders?.length) {
        // 首页聚合可能不全；仍拉完整列表
      }
    } catch {
      /* ignore */
    }
    const list = await api<Reminder[]>('/api/reminders')
    remindCache.current = list
    return list
  }

  async function ensureNoticeList() {
    if (noticeCache.current) return noticeCache.current
    const list = await api<Notice[]>('/api/notices')
    noticeCache.current = list
    return list
  }

  async function ensureEventList() {
    if (eventCache.current) return eventCache.current
    try {
      const data = await ensureHomeSnap()
      if (data.upcoming_events?.length) {
        eventCache.current = data.upcoming_events
        return data.upcoming_events
      }
    } catch {
      /* ignore */
    }
    const list = await api<CalendarEvent[]>('/api/schedule/events')
    eventCache.current = list
    return list
  }

  async function ensureCommunityList() {
    if (communityCache.current) return communityCache.current
    const list = await api<CommunityPostBrief[]>('/api/community/posts')
    communityCache.current = list
    return list
  }

  /** 进入「今日安排」前拉取课次，生成最多 5 个第三层球体 */
  async function prepareTodayLayer() {
    let slots: ScheduleSlot[] = []
    try {
      const data = await ensureHomeSnap()
      slots = data.today_slots ?? []
      if (!slots.length) {
        slots = await api<ScheduleSlot[]>('/api/schedule/today')
        const merged = { ...data, today_slots: slots }
        homeCache.current = merged
      }
    } catch {
      try {
        slots = await api<ScheduleSlot[]>('/api/schedule/today')
      } catch {
        slots = []
      }
    }
    applyTodaySlotChildren(slots)
  }

  /** 进入「本周」前拉取整周课表，生成周一…周五 5 球 */
  async function prepareWeekLayer() {
    const slots = await ensureWeekSlots()
    applyWeekDayChildren(slots)
  }

  async function prepareRemindLayer(kind: 'due' | 'online') {
    const list = await ensureRemindList()
    applyRemindChildren(kind, list)
  }

  async function prepareNoticeLayer(kind: 'school' | 'urgent') {
    const list = await ensureNoticeList()
    applyNoticeChildren(kind, list)
  }

  async function prepareEventLayer(kind: 'exam' | 'holiday') {
    const list = await ensureEventList()
    applyEventChildren(kind, list)
  }

  async function prepareCommunityLayer(kind: 'feed' | 'pics') {
    const list = await ensureCommunityList()
    applyCommunityChildren(kind, list)
  }

  const activeSlot = infoCardId && isSlotNodeId(infoCardId) ? slotByNodeId[infoCardId] : null
  const activeDaySlots =
    infoCardId && isDayNodeId(infoCardId) ? daySlotsByNodeId[infoCardId] ?? [] : null
  const activeDayLabel =
    infoCardId && isDayNodeId(infoCardId)
      ? weekdayLabel(Number(infoCardId.slice(DAY_PREFIX.length)))
      : ''
  const activeRem = infoCardId && isRemNodeId(infoCardId) ? remByNodeId[infoCardId] : null
  const activeNotice =
    infoCardId && isNoticeNodeId(infoCardId) ? noticeByNodeId[infoCardId] : null
  const activeEvent =
    infoCardId && isEventNodeId(infoCardId) ? eventByNodeId[infoCardId] : null
  const activePost =
    infoCardId && isPostNodeId(infoCardId) ? postByNodeId[infoCardId] : null

  function handleNodeTap(id: string) {
    if (transitioningRef.current) return
    if (id === primaryIdRef.current) {
      closeInfoCard()
      if (pathRef.current.length > 1) void goBackLayer()
      return
    }
    // 不可下钻：详情卡（含第三层课次球）
    if (!canDrillFrom(pathRef.current.length, id)) {
      focusNode(id)
      void openInfoCard(id)
      return
    }
    closeInfoCard()
    void enterLayer(id)
  }

  /**
   * 子键 → 主键过渡（同一画布，不换页）：
   * 1. 寻找节点特效
   * 2. 隐藏同层其它子键
   * 3. 下层新子键 + 连线浮出水面
   * （一→二 与 二→三 共用）
   */
  async function enterLayer(id: string) {
    if (transitioningRef.current) return
    if (id === primaryIdRef.current) return
    if (!canDrillFrom(pathRef.current.length, id)) return
    transitioningRef.current = true

    // 进入第三层前准备动态子球，再走同一套搜寻/浮出
    if (id === 'today') await prepareTodayLayer()
    else if (id === 'week') await prepareWeekLayer()
    else if (id === 'due' || id === 'online') await prepareRemindLayer(id)
    else if (id === 'school' || id === 'urgent') await prepareNoticeLayer(id)
    else if (id === 'feed' || id === 'pics') await prepareCommunityLayer(id)
    else if (id === 'exam' || id === 'holiday') await prepareEventLayer(id)

    const label = NODE_CATALOG[id]?.label || dynamicMeta[id]?.label || id
    const onScreen = nodesRef.current.some((n) => n.id === id)

    if (onScreen) {
      await seekNodeToCenter(id, {
        hideOthers: true,
        label: `正在定位 · ${label}`,
        keepSeeking: true,
      })
    } else {
      setDimmedIds(nodesRef.current.map((n) => n.id))
      setEdgesReady(false)
      setSeeking(true)
      setSeekLabel(`正在定位 · ${label}`)
      await new Promise<void>((r) => {
        window.setTimeout(r, 480)
      })
    }

    revealLayer(id, [...pathRef.current, id])
    transitioningRef.current = false
  }

  async function goBackLayer() {
    if (transitioningRef.current) return
    if (pathRef.current.length <= 1) return
    transitioningRef.current = true

    const nextPath = pathRef.current.slice(0, -1)
    const nextPrimary = nextPath[nextPath.length - 1]
    const label =
      nextPrimary === ROOT_ID
        ? user?.full_name?.slice(0, 1) || '我'
        : NODE_CATALOG[nextPrimary]?.label || nextPrimary
    const cur = primaryIdRef.current

    // 1) 第二层子键沉入水面，连线先收起（仍同一页）
    const childIds = nodesRef.current.filter((n) => n.id !== cur).map((n) => n.id)
    setEdgesReady(false)
    if (childIds.length) {
      setSinkingIds(childIds)
      await wait(380)
      const onlyPrimary = nodesRef.current.filter((n) => n.id === cur)
      targetsRef.current = onlyPrimary
      nodesRef.current = onlyPrimary
      setNodes(onlyPrimary)
      setSinkingIds([])
    }

    // 2) 搜寻过渡到上层主键位置感
    if (nodesRef.current.some((n) => n.id === cur)) {
      await seekNodeToCenter(cur, {
        hideOthers: true,
        label: `返回 · ${label}`,
        keepSeeking: true,
      })
    }

    // 3) 上层子键浮出水面；回到第一层时刷新无连线提醒球
    if (nextPrimary === ROOT_ID) {
      await refreshFloatReminders()
    }
    revealLayer(nextPrimary, nextPath)
    transitioningRef.current = false
  }

  /** 只复位当前层球的位置（不退回上一层 / 不换主键） */
  function resetLayout() {
    if (transitioningRef.current) return
    const stage = stageRef.current
    const w = Math.max(stage?.clientWidth || 0, sizeRef.current.w, size.w, 320)
    const h = Math.max(stage?.clientHeight || 0, sizeRef.current.h, size.h, 400)
    sizeRef.current = { w, h }
    setSize({ w, h })

    const primary = primaryIdRef.current
    const keep = new Map(
      nodesRef.current
        .filter((n) => isFloatRemNodeId(n.id))
        .map((n) => [n.id, { x: n.x, y: n.y }]),
    )
    const laid = layoutLayer(
      w,
      h,
      primary,
      user?.full_name || '我',
      layoutOptsFor(primary, keep),
    )

    dragIdRef.current = null
    dragPointerRef.current = null
    setDragId(null)
    setBumpedIds([])
    setDimmedIds([])
    setSeeking(false)
    setSeekLabel('')
    setSeekFocusId(null)
    setPan({ x: 0, y: 0 })
    panRef.current = { x: 0, y: 0 }
    setEdgesReady(true)
    setEnteringIds([])
    setSinkingIds([])
    setPrimarySettle(false)
    setInfoCardId(null)
    setSelected(primary)

    targetsRef.current = laid
    nodesRef.current = laid
    setNodes(laid)
    setLocateId(primary)
    if (locateTimer.current) window.clearTimeout(locateTimer.current)
    locateTimer.current = window.setTimeout(() => setLocateId(null), 700)
  }

  async function jumpToPathIndex(index: number) {
    if (transitioningRef.current) return
    if (index < 0 || index >= pathRef.current.length - 1) return
    // 与返回上层同一套沉入 → 搜寻 → 浮出
    if (index === pathRef.current.length - 2) {
      await goBackLayer()
      return
    }
    transitioningRef.current = true
    const nextPath = pathRef.current.slice(0, index + 1)
    const nextPrimary = nextPath[nextPath.length - 1]
    const label =
      nextPrimary === ROOT_ID
        ? user?.full_name?.slice(0, 1) || '我'
        : NODE_CATALOG[nextPrimary]?.label || nextPrimary
    const cur = primaryIdRef.current

    const childIds = nodesRef.current.filter((n) => n.id !== cur).map((n) => n.id)
    setEdgesReady(false)
    if (childIds.length) {
      setSinkingIds(childIds)
      await wait(380)
      const onlyPrimary = nodesRef.current.filter((n) => n.id === cur)
      targetsRef.current = onlyPrimary
      nodesRef.current = onlyPrimary
      setNodes(onlyPrimary)
      setSinkingIds([])
    }

    if (nodesRef.current.some((n) => n.id === cur)) {
      await seekNodeToCenter(cur, {
        hideOthers: true,
        label: `返回 · ${label}`,
        keepSeeking: true,
      })
    }
    if (nextPrimary === ROOT_ID) {
      await refreshFloatReminders()
    }
    revealLayer(nextPrimary, nextPath)
    transitioningRef.current = false
  }

  function onNodePointerDown(id: string, e: ReactPointerEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    panningRef.current = false
    setCanvasPanning(false)

    const stage = stageRef.current
    const node = targetsRef.current.find((n) => n.id === id) ?? nodesRef.current.find((n) => n.id === id)
    if (!stage || !node) return

    const rect = stage.getBoundingClientRect()
    const px = e.clientX - rect.left - panRef.current.x
    const py = e.clientY - rect.top - panRef.current.y
    dragGrabRef.current = { x: px - node.x, y: py - node.y }
    dragPointerRef.current = e.pointerId
    dragIdRef.current = id
    pointerStartRef.current = { x: e.clientX, y: e.clientY }
    didDragRef.current = false
    setDragId(id)
    setSelected(id)

    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch {
      /* ignore */
    }
  }

  function onNodePointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    if (dragPointerRef.current !== e.pointerId || !dragIdRef.current) return
    e.preventDefault()
    e.stopPropagation()

    const dx = e.clientX - pointerStartRef.current.x
    const dy = e.clientY - pointerStartRef.current.y
    if (!didDragRef.current) {
      if (Math.hypot(dx, dy) < CLICK_DRAG_THRESHOLD) return
      didDragRef.current = true
    }
    applyDragAt(e.clientX, e.clientY)
  }

  function onNodePointerUp(e: ReactPointerEvent<HTMLDivElement>) {
    if (dragPointerRef.current !== null && e.pointerId !== dragPointerRef.current) return
    const id = dragIdRef.current
    const wasDrag = didDragRef.current
    try {
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId)
      }
    } catch {
      /* ignore */
    }
    endNodeDrag()

    // 轻点立刻切换主键（无搜寻停顿）；双击仍可打开页面
    if (!wasDrag && id) {
      handleNodeTap(id)
    }
  }

  function onNodeDoubleClick(_id: string, to?: string) {
    if (to) navigate(to)
  }

  function onStagePointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    const t = e.target as HTMLElement
    if (
      t.closest('.neo-node') ||
      t.closest('.neo-key') ||
      t.closest('.neo-side') ||
      t.closest('.neo-info-card')
    ) {
      return
    }
    if (dragIdRef.current) return
    panningRef.current = true
    setCanvasPanning(true)
    setPanAnim(false)
    panStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      panX: panRef.current.x,
      panY: panRef.current.y,
    }
    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch {
      /* ignore */
    }
  }

  function onStagePointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    if (!panningRef.current) return
    const next = {
      x: panStartRef.current.panX + (e.clientX - panStartRef.current.x),
      y: panStartRef.current.panY + (e.clientY - panStartRef.current.y),
    }
    panRef.current = next
    setPan(next)
  }

  function onStagePointerUp(e: ReactPointerEvent<HTMLDivElement>) {
    if (!panningRef.current) return
    panningRef.current = false
    setCanvasPanning(false)
    setPanAnim(true)
    try {
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId)
      }
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="screen home-neo">
      <header className="neo-bar">
        <div className="neo-brand">
          <span className="neo-dot" />
          <div>
            <strong>小医</strong>
            <em>你好，{user?.full_name}</em>
          </div>
        </div>
        <div className="neo-bar-actions">
          {/* 管理员专属入口：替其它用户开通课程/服务、下发监督提醒 */}
          {isAdmin && (
            <button
              type="button"
              className="neo-chip"
              onClick={() => navigate('/admin-user')}
              title="替其它用户代办课程、服务与监督提醒"
            >
              用户
            </button>
          )}
          {path.length > 1 && (
            <button type="button" className="neo-chip ghost" onClick={goBackLayer}>
              返回
            </button>
          )}
          <button
            type="button"
            className="neo-chip ghost"
            onClick={resetLayout}
            title="复位当前层节点位置"
          >
            复位
          </button>
          <span className="neo-chip">
            第{layerDepth}层 · {primaryLabel}
          </span>
        </div>
      </header>

      {path.length > 1 && (
        <div className="neo-crumb" aria-label="层级路径">
          {path.map((id, i) => {
            const label =
              id === ROOT_ID
                ? user?.full_name?.slice(0, 1) || '我'
                : NODE_CATALOG[id]?.label || id
            const last = i === path.length - 1
            return (
              <span key={`${id}-${i}`} className="neo-crumb-item">
                {i > 0 && <i>/</i>}
                <button
                  type="button"
                  className={last ? 'current' : ''}
                  disabled={last}
                  onClick={() => {
                    if (last) return
                    void jumpToPathIndex(i)
                  }}
                >
                  {label}
                </button>
              </span>
            )
          })}
        </div>
      )}

      <div className={`neo-body${sideOpen ? ' side-open' : ' side-closed'}`}>
        <aside
          id="neo-side-panel"
          className={`neo-side${sideOpen ? ' open' : ''}`}
          aria-hidden={!sideOpen}
        >
          <div className="neo-side-head">
            <p className="neo-side-title">本层节点</p>
            <button
              type="button"
              className="neo-side-close"
              onClick={() => setSideOpen(false)}
              aria-label="收起节点导航"
            >
              ×
            </button>
          </div>
          <ul>
            {nodes.map((n) => {
              const canPromote = n.id !== primaryId && canDrillFrom(path.length, n.id)
              return (
                <li key={n.id}>
                  <button
                    type="button"
                    className={selected === n.id ? 'active' : ''}
                    onClick={() => {
                      if (n.id === primaryId) focusNode(n.id)
                      else if (canPromote) void enterLayer(n.id)
                      else focusNode(n.id)
                    }}
                  >
                    <i className={`tone ${n.tone}`} />
                    <span className="neo-side-label">{n.label}</span>
                    {canPromote && <em className="neo-side-tag">下层</em>}
                    {n.id !== primaryId && !canPromote && (
                      <em className="neo-side-tag leaf">子键</em>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
          {selectedNode && (
            <div className="neo-detail">
              <strong>{selectedNode.label}</strong>
              <p>{selectedNode.sub}</p>
              <div className="neo-detail-actions">
                {selectedNode.id !== primaryId && canDrillFrom(path.length, selectedNode.id) && (
                  <button
                    type="button"
                    className="btn primary block small"
                    onClick={() => void enterLayer(selectedNode.id)}
                  >
                    设为主键
                  </button>
                )}
                {selectedNode.id === primaryId && path.length > 1 && (
                  <button
                    type="button"
                    className="btn block small"
                    onClick={() => void goBackLayer()}
                  >
                    返回上层
                  </button>
                )}
                {selectedNode.to && (
                  <button
                    type="button"
                    className="btn block small"
                    onClick={() => navigate(selectedNode.to!)}
                  >
                    打开页面
                  </button>
                )}
              </div>
            </div>
          )}
        </aside>

        <div
          className={`neo-stage${seeking ? ' seeking' : ''}${canvasPanning ? ' panning' : ''}${dragId ? ' dragging-node' : ''}${dimmedIds.length ? ' dimming' : ''}${!edgesReady ? ' edges-pending' : ''}`}
          ref={stageRef}
          onPointerDown={onStagePointerDown}
          onPointerMove={onStagePointerMove}
          onPointerUp={onStagePointerUp}
          onPointerCancel={onStagePointerUp}
        >
          <div className="neo-bg-seek" aria-hidden="true" />
          <div className="neo-seek-cross" aria-hidden="true" />
          {(enteringIds.length > 0 || sinkingIds.length > 0) && (
            <div className="neo-water-line" aria-hidden="true" />
          )}
          {seeking && (
            <div className="neo-seek-banner" aria-live="polite">
              {seekLabel}
            </div>
          )}

          <button
            type="button"
            className={`neo-key on-stage${sideOpen ? ' on' : ''}`}
            onClick={() => setSideOpen((v) => !v)}
            aria-expanded={sideOpen}
            aria-controls="neo-side-panel"
            title={sideOpen ? '收起节点导航' : '展开节点导航'}
          >
            <span className="neo-key-lines" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <em>{sideOpen ? '收起' : '节点'}</em>
          </button>

          <div
            className={`neo-world${seeking ? ' seeking-move' : ''}${panAnim ? '' : ' no-anim'}`}
            style={{ transform: `translate3d(${pan.x}px, ${pan.y}px, 0)` }}
          >
            <svg
              key={`edges-${primaryId}-${edgeAnimKey}`}
              className={`neo-edges${edgesReady ? ' edges-on edges-emerge' : ' edges-off'}`}
              width={worldBox.w}
              height={worldBox.h}
              viewBox={`${worldBox.x} ${worldBox.y} ${worldBox.w} ${worldBox.h}`}
              style={{ left: worldBox.x, top: worldBox.y }}
            >
              {layerEdges.map((e) => {
                const a = byId.get(e.from)
                const b = byId.get(e.to)
                if (!a || !b) return null
                if (dimmedSet.has(e.from) || dimmedSet.has(e.to)) return null
                const active =
                  selected === e.from || selected === e.to || dragId === e.from || dragId === e.to
                return (
                  <g key={`${e.from}-${e.to}`} className={active ? 'edge-active' : ''}>
                    <line
                      x1={a.x}
                      y1={a.y}
                      x2={b.x}
                      y2={b.y}
                      className="neo-edge soft-edge"
                    />
                    <line
                      x1={a.x}
                      y1={a.y}
                      x2={b.x}
                      y2={b.y}
                      className="neo-edge-flow"
                    />
                  </g>
                )
              })}
            </svg>

            {nodes.map((n, i) => {
              const showAvatar = n.id === ROOT_ID && !!user?.avatar_url
              const isPrimary = n.id === primaryId
              const drillable = !isPrimary && canDrillFrom(path.length, n.id)
              const entering = enteringSet.has(n.id)
              const sinking = sinkingSet.has(n.id)
              const dimmed = dimmedSet.has(n.id)
              const seekingFocus = seekFocusId === n.id
              const floatRem = isFloatRemNodeId(n.id)
              const floatUrg =
                floatRem && remByNodeId[n.id]
                  ? reminderUrgency(remByNodeId[n.id].due_at, nowTick)
                  : null
              const floatVanishing = floatRem && vanishingRemIds.includes(n.id)
              return (
                <div
                  key={n.id}
                  role="button"
                  tabIndex={0}
                  title={
                    isPrimary
                      ? path.length > 1
                        ? '点击返回上层'
                        : '当前主键'
                      : floatRem
                        ? '提醒（无连线）· 点击查看截止倒计时'
                        : drillable
                          ? '点击搜寻并设为主键 · 双击打开页面'
                          : isL3LeafId(n.id)
                            ? '点击查看详情 · 双击打开页面'
                            : LEAF_CARDS[n.id]
                              ? '点击查看详情卡 · 双击打开页面'
                              : '子键 · 可拖动 / 双击打开页面'
                  }
                  className={`neo-node ${isPrimary || seekingFocus ? 'center' : n.tone}${selected === n.id ? ' selected' : ''}${locateId === n.id ? ' locate' : ''}${dragId === n.id ? ' dragging' : ''}${bumpedIds.includes(n.id) ? ' bumped' : ''}${showAvatar ? ' has-photo' : ''}${isPrimary || seekingFocus ? ' is-primary' : ' is-child'}${drillable ? ' drillable' : ''}${entering ? ' emerge-water' : ''}${sinking ? ' sink-water' : ''}${dimmed ? ' neo-dim' : ''}${seekingFocus ? ' seek-focus' : ''}${isPrimary && primarySettle ? ' primary-settle' : ''}${floatRem ? ` float-rem urgency-${floatUrg}` : ''}${floatVanishing ? ' float-rem-vanish' : ''}`}
                  style={{
                    left: Number.isFinite(n.x) ? n.x : 0,
                    top: Number.isFinite(n.y) ? n.y : 0,
                    ['--ripple-delay' as string]: `${(i % 5) * 0.35}s`,
                    ['--enter-delay' as string]: `${Math.min(i, 6) * 0.07}s`,
                  }}
                  onPointerDown={(e) => onNodePointerDown(n.id, e)}
                  onPointerMove={onNodePointerMove}
                  onPointerUp={onNodePointerUp}
                  onPointerCancel={onNodePointerUp}
                  onDoubleClick={() => onNodeDoubleClick(n.id, n.to)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      handleNodeTap(n.id)
                    }
                  }}
                >
                  <span className="node-ripple" aria-hidden="true" />
                  {entering && <span className="emerge-sheen" aria-hidden="true" />}
                  {drillable && !floatRem && <span className="neo-drill-mark" aria-hidden="true" />}
                  {showAvatar ? (
                    <img className="neo-node-photo" src={user.avatar_url} alt="" draggable={false} />
                  ) : (
                    <>
                      <span className="neo-node-core">{n.label}</span>
                      <span className="neo-node-sub">
                        {floatRem && remByNodeId[n.id]
                          ? formatCountdown(remByNodeId[n.id].due_at, nowTick)
                          : n.sub}
                      </span>
                    </>
                  )}
                </div>
              )
            })}
          </div>

          {infoCardId && activeSlot && (
            <div className="neo-info-card" role="dialog" aria-label={activeSlot.course_name}>
              <header className="neo-info-card-head">
                <div>
                  <strong>{activeSlot.course_name}</strong>
                  <em>今日课次 · 含上课地点</em>
                </div>
                <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                  ×
                </button>
              </header>
              <div className="neo-info-body">
                <ul className="neo-info-list">
                  <li>
                    <strong>时间</strong>
                    <span>
                      {activeSlot.start_time} – {activeSlot.end_time}
                    </span>
                  </li>
                  <li>
                    <strong>地点</strong>
                    <span>{activeSlot.location || '待定'}</span>
                  </li>
                </ul>
                <button
                  type="button"
                  className="btn primary block small"
                  onClick={() => navigate('/schedule')}
                >
                  打开课表页
                </button>
              </div>
            </div>
          )}

          {infoCardId && activeDaySlots && (
            <div className="neo-info-card" role="dialog" aria-label={activeDayLabel}>
              <header className="neo-info-card-head">
                <div>
                  <strong>{activeDayLabel}</strong>
                  <em>当天课程 · 含上课地点（最多 5 节）</em>
                </div>
                <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                  ×
                </button>
              </header>
              <div className="neo-info-body">
                {activeDaySlots.length === 0 ? (
                  <p className="neo-info-empty">当天暂无课程</p>
                ) : (
                  <ul className="neo-info-list">
                    {activeDaySlots.map((s) => (
                      <li key={s.id}>
                        <strong>{s.course_name}</strong>
                        <span>
                          {s.start_time} – {s.end_time}
                        </span>
                        <em>地点 · {s.location || '待定'}</em>
                      </li>
                    ))}
                  </ul>
                )}
                <button
                  type="button"
                  className="btn primary block small"
                  onClick={() => navigate('/schedule')}
                >
                  打开课表页
                </button>
              </div>
            </div>
          )}

          {infoCardId && activeRem && (() => {
            const urg = reminderUrgency(activeRem.due_at, nowTick)
            const leftLabel = formatCountdown(activeRem.due_at, nowTick)
            const ratio = remainRatio(activeRem.due_at, nowTick)
            return (
              <div
                className={`neo-info-card neo-rem-card${isFloatRemNodeId(infoCardId) ? ' compact' : ''} urgency-${urg}`}
                role="dialog"
                aria-label={activeRem.title}
              >
                <header className="neo-info-card-head">
                  <div>
                    <strong>{activeRem.title}</strong>
                    <em>
                      {activeRem.course_name}
                      {isFloatRemNodeId(infoCardId) ? ' · 无连线提醒' : ''}
                    </em>
                  </div>
                  <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                    ×
                  </button>
                </header>
                <div className="neo-info-body">
                  <div className="neo-rem-countdown" aria-live="polite">
                    <span>剩余</span>
                    <strong>{leftLabel}</strong>
                  </div>
                  <div className="neo-rem-bar" aria-hidden="true">
                    <i style={{ transform: `scaleX(${ratio})` }} />
                  </div>
                  <ul className="neo-info-list">
                    <li>
                      <strong>截止</strong>
                      <span>{formatDateTime(activeRem.due_at)}</span>
                    </li>
                    {activeRem.content && (
                      <li>
                        <strong>内容</strong>
                        <span>{activeRem.content}</span>
                      </li>
                    )}
                  </ul>
                  {activeRem.external_url && (
                    <a
                      className="btn primary block small"
                      href={activeRem.external_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      打开网课链接
                    </a>
                  )}
                  <button
                    type="button"
                    className="btn block small"
                    onClick={() => navigate('/reminders')}
                  >
                    打开提醒页
                  </button>
                </div>
              </div>
            )
          })()}

          {infoCardId && activeNotice && (
            <div className="neo-info-card" role="dialog" aria-label={activeNotice.title}>
              <header className="neo-info-card-head">
                <div>
                  <strong>
                    {activeNotice.title}
                    {activeNotice.is_urgent ? ' · 紧急' : ''}
                  </strong>
                  <em>
                    {activeNotice.audience === 'teacher'
                      ? '管理'
                      : activeNotice.audience === 'student'
                        ? '用户'
                        : '全部'}{' '}
                    · {formatDate(activeNotice.created_at)}
                  </em>
                </div>
                <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                  ×
                </button>
              </header>
              <div className="neo-info-body">
                <p className="neo-info-empty" style={{ whiteSpace: 'pre-wrap' }}>
                  {activeNotice.body.slice(0, 180)}
                  {activeNotice.body.length > 180 ? '…' : ''}
                </p>
                <button
                  type="button"
                  className="btn primary block small"
                  onClick={() => navigate(`/notices/${activeNotice.id}`)}
                >
                  查看公告全文
                </button>
              </div>
            </div>
          )}

          {infoCardId && activeEvent && (
            <div className="neo-info-card" role="dialog" aria-label={activeEvent.title}>
              <header className="neo-info-card-head">
                <div>
                  <strong>{activeEvent.title}</strong>
                  <em>校历 · {formatDate(activeEvent.event_date)}</em>
                </div>
                <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                  ×
                </button>
              </header>
              <div className="neo-info-body">
                <p className="neo-info-empty">{activeEvent.description || '暂无补充说明'}</p>
                <button
                  type="button"
                  className="btn primary block small"
                  onClick={() => navigate('/schedule')}
                >
                  打开课表 / 校历
                </button>
              </div>
            </div>
          )}

          {infoCardId && activePost && (
            <div className="neo-info-card" role="dialog" aria-label="社区动态">
              <header className="neo-info-card-head">
                <div>
                  <strong>{activePost.author_name || '用户'}</strong>
                  <em>社区 · {formatDateTime(activePost.created_at)}</em>
                </div>
                <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                  ×
                </button>
              </header>
              <div className="neo-info-body">
                {activePost.content ? (
                  <p className="neo-info-empty" style={{ whiteSpace: 'pre-wrap' }}>
                    {activePost.content.slice(0, 180)}
                    {activePost.content.length > 180 ? '…' : ''}
                  </p>
                ) : (
                  <p className="neo-info-empty">照片动态</p>
                )}
                {activePost.image_urls?.length > 0 && (
                  <div className="neo-post-thumbs">
                    {activePost.image_urls.slice(0, 3).map((url) => (
                      <img key={url} src={url} alt="" />
                    ))}
                  </div>
                )}
                <button
                  type="button"
                  className="btn primary block small"
                  onClick={() => navigate('/community')}
                >
                  打开社区
                </button>
              </div>
            </div>
          )}

          {infoCardId &&
            !activeSlot &&
            !activeDaySlots &&
            !activeRem &&
            !activeNotice &&
            !activeEvent &&
            !activePost &&
            LEAF_CARDS[infoCardId] && (() => {
              const card = LEAF_CARDS[infoCardId]
              const go = card.to || NODE_CATALOG[infoCardId]?.to
              return (
                <div className="neo-info-card" role="dialog" aria-label={card.title}>
                  <header className="neo-info-card-head">
                    <div>
                      <strong>{card.title}</strong>
                      {card.blurb && <em>{card.blurb}</em>}
                    </div>
                    <button type="button" className="neo-info-close" onClick={closeInfoCard} aria-label="关闭">
                      ×
                    </button>
                  </header>
                  <div className="neo-info-body">
                    <p className="neo-info-empty">{card.blurb}</p>
                    {go && (
                      <button
                        type="button"
                        className="btn primary block small"
                        onClick={() => navigate(go)}
                      >
                        打开完整页面
                      </button>
                    )}
                  </div>
                </div>
              )
            })()}

          <p className="neo-hint">
            左侧无连线球=临期提醒 · 点开看倒计时变色 · 到期自动消失
          </p>
        </div>
      </div>
    </div>
  )
}
