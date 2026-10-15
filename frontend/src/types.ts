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
