export type Role = 'student' | 'teacher' | 'admin'

export interface User {
  id: number
  username: string
  full_name: string
  role: Role
  avatar_url?: string
}

export interface Notice {
  id: number
  title: string
  body: string
  audience: string
  is_urgent?: boolean
  author_id: number
  author_name: string
  created_at: string
}

export interface Course {
  id: number
  name: string
  semester: string
  teacher_id: number | null
  teacher_name: string
  description: string
  price: number
  cover_url?: string
  enrolled?: boolean
  /** 商城字段：课程类型（single / bundle）、路径标签、副标题 */
  course_type?: string
  path_label?: string
  tagline?: string
  lesson_count?: number
}

export interface Lesson {
  id: number
  course_id: number
  title: string
  summary: string
  video_url: string
  duration_seconds: number
  sort_order: number
  is_trial: boolean
  /** 未购买且非试看时为 true，此时 video_url 为空 */
  locked: boolean
}

export interface CourseLessons {
  course_id: number
  course_name: string
  owned: boolean
  is_free: boolean
  trial_lesson_count: number
  total_lessons: number
  completed_lessons: number
  progress_percent: number
  lessons: Lesson[]
}

export interface ServiceProduct {
  id: number
  name: string
  category: string
  description: string
  price: number
  cover_url?: string
  unit_label?: string
  owned?: boolean
}

export type ReminderKind = 'general' | 'medication' | 'checkup'
export type RepeatRule = 'none' | 'daily' | 'weekly'

export interface Reminder {
  id: number
  course_id: number | null
  course_name: string
  title: string
  content: string
  due_at: string
  external_url: string
  creator_id: number
  /** 管理员点名下发给某个用户时才有值 */
  target_user_id?: number | null
  created_at: string
  status: 'pending' | 'overdue'
  source?: 'user' | 'manager' | 'system'
  notify_enabled?: boolean
  can_delete?: boolean
  can_edit?: boolean
  completed?: boolean
  completed_at?: string | null
  kind: ReminderKind
  drug_name: string
  dosage: string
  repeat_rule: RepeatRule
  check_type: string
  prep_questions: string
  recurring_parent_id?: number | null
}

export interface ScheduleSlot {
  id: number
  course_id: number
  course_name: string
  weekday: number
  start_time: string
  end_time: string
  location: string
}

export interface CalendarEvent {
  id: number
  title: string
  event_date: string
  description: string
}

export interface HomeData {
  today_slots: ScheduleSlot[]
  upcoming_reminders: Reminder[]
  latest_notices: Notice[]
  upcoming_events: CalendarEvent[]
}

export interface CourseMaterial {
  id: number
  course_id: number
  course_name: string
  title: string
  url: string
  note: string
  creator_id: number
  created_at: string
  can_delete: boolean
}

/** 管理员代办页的一次性数据（routers/admin.py 的 overview） */
export interface AdminOverview {
  user: User
  courses: Course[]
  services: ServiceProduct[]
  reminders: Reminder[]
}

export interface GradeItem {
  id: number
  course_id: number
  course_name: string
  student_id: number
  student_name: string
  title: string
  score: number
  remark: string
  creator_id: number
  created_at: string
  can_delete: boolean
}

// ---------- 好友（routers/friends.py）----------

export type FriendState = 'self' | 'none' | 'pending_out' | 'pending_in' | 'friends'

/** 好友 / 申请人 / 搜索结果的统一用户视图 */
export interface FriendUser {
  user_id: number
  username: string
  full_name: string
  role: Role
  avatar_url: string
  friend_state: FriendState
}

export interface Friend extends FriendUser {
  last_message: string
  last_message_at: string | null
  unread_count: number
}

export interface FriendRequestItem extends FriendUser {
  request_id: number
  created_at: string
  direction: 'incoming' | 'outgoing'
}

export interface FriendMessage {
  id: number
  sender_id: number
  recipient_id: number
  content: string
  created_at: string
  mine: boolean
}

export interface FriendSummary {
  pending_requests: number
  unread_messages: number
  total: number
}

export interface FriendActionResult {
  request_id: number | null
  user_id: number
  status: 'pending' | 'accepted'
  auto_accepted: boolean
}

// ---------- 商城订单 / 我的课程（routers/mall.py）----------

export interface MallMyCourse {
  course: Course & { expires_at?: string | null }
  source: string
  expires_at: string | null
  total_lessons: number
  completed_lessons: number
  progress_percent: number
}

export type MallOrderStatus =
  | 'pending'
  | 'paid'
  | 'cancelled'
  | 'refund_pending'
  | 'refunded'
  | 'partially_refunded'
  | string

export interface MallOrderSeat {
  id: number
  learner_user_id: number | null
  learner_name: string
  learner_phone: string
  activation_code: string
  status: string
  activated_at: string | null
  refund_amount: number
  refunded_at: string | null
}

export interface MallOrder {
  id: number
  order_no: string
  product_type: 'course' | 'service'
  product_id: number
  product_name: string
  product_cover: string
  product_category: string
  quantity: number
  unit_price: number
  original_amount: number
  discount_amount: number
  amount: number
  status: MallOrderStatus
  channel: string
  order_type: string
  transaction_id: string
  buyer_id: number
  buyer_name: string
  created_at: string
  expires_at: string | null
  paid_at: string | null
  valid_until: string | null
  cancelled_at: string | null
  refunded_at: string | null
  refund_amount: number
  refund_reason: string
  upgrade_from_order_id: number | null
  upgrade_source_order_nos: string[]
  seats: MallOrderSeat[]
  can_pay: boolean
  can_cancel: boolean
  refundable: boolean
  refund_hint: string
}

export interface MallOrderList {
  items: MallOrder[]
  total: number
  page: number
  page_size: number
}

export interface MallRefundCheck {
  eligible: boolean
  reason: string
  refund_amount: number
  within_window: boolean
  window_ends_at: string | null
  progress_percent: number
  policy: string
}

export interface MallRefundPolicy {
  policy: string
  window_days: number
  progress_limit: number
  order_ttl_minutes: number
  auto_refund: boolean
}

// ---------- 医院资料（routers/hospital.py）----------

export interface HospitalPartner {
  id: number
  code: string
  name: string
  department: string
  status: string
  mode: string
  contact: string
  note: string
}

export interface HospitalAuthorization {
  id: number
  partner_id: number
  partner_name: string
  patient_ref_masked: string
  scopes: string[]
  status: 'active' | 'expired' | 'revoked' | string
  authorized_at: string
  expires_at: string | null
  revoked_at: string | null
}

export type HospitalRecordType = 'advice' | 'condition' | 'record'

export interface HospitalRecord {
  id: number
  partner_id: number
  partner_name: string
  record_type: HospitalRecordType
  title: string
  content: string
  doctor_name: string
  department: string
  occurred_at: string | null
  fetched_at: string
}

export interface HospitalCaregiver {
  id: number
  patient_user_id: number
  patient_name: string
  caregiver_user_id: number
  caregiver_name: string
  relation: string
  status: 'active' | 'revoked' | string
  granted_at: string
  revoked_at: string | null
}

export interface HospitalCaregivers {
  granted: HospitalCaregiver[]
  received: HospitalCaregiver[]
}

// ---------- AI 用药动作检测（routers/ai.py）----------

export type MedicationMode = 'oral' | 'inhale'

export interface MedicationStep {
  name: string
  done: boolean
}

export interface MedicationCheck {
  id: number
  user_id: number
  lesson_id: number | null
  status: string
  provider: string
  mode: MedicationMode
  steps: MedicationStep[]
  needs_retry: boolean
  message: string
  image_size: number
  image_type: string
  created_at: string
  expires_at: string | null
  disclaimer: string
}

export interface MedicationCheckList {
  items: MedicationCheck[]
  total: number
  page: number
  page_size: number
  retention_days: number
  disclaimer: string
}

// ---------- 症状日记（routers/symptoms.py）----------

export interface SymptomEntry {
  id: number
  record_date: string
  cough: number
  dyspnea: number
  sputum: number
  note: string
  total: number
  warning: boolean
  warning_text: string
  created_at: string
  updated_at: string
}

export interface SymptomDiary {
  items: SymptomEntry[]
  warning: boolean
  warning_text: string
  disclaimer: string
}

// ---------- 消息通知与手机推送（routers/notifications.py）----------

export interface AppNotification {
  id: number
  user_id: number
  reminder_id: number
  course_id: number | null
  course_name: string
  trigger_key: string
  title: string
  body: string
  external_url: string
  due_at: string | null
  created_at: string
  read_at: string | null
  read: boolean
  click_url: string
}

export interface NotificationList {
  items: AppNotification[]
  total: number
  unread: number
  page: number
  page_size: number
}

export interface PushConfig {
  enabled: boolean
  public_key: string
  subject: string
  reason: string
}

export interface PushStatus {
  enabled: boolean
  reason: string
  subscriptions: number
  last_success_at: string | null
}

export interface PushTestResult {
  ok: boolean
  sent: number
  failed: number
  total: number
  detail: string
}
