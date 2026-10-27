from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str
    avatar_url: str = ""


class AvatarPreviewOut(BaseModel):
    username: str
    avatar_url: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    role: str = Field(pattern="^(student|teacher|admin)$")


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    old_password: str | None = None
    new_password: str | None = Field(default=None, min_length=4, max_length=128)


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    audience: str = Field(default="all", pattern="^(all|student|teacher)$")
    is_urgent: bool = False


class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    audience: str
    is_urgent: bool = False
    author_id: int
    author_name: str = ""
    created_at: datetime


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    semester: str = Field(default="COPD 系列", max_length=40)
    teacher_id: int | None = None
    description: str = ""
    price: float = Field(default=2.99, ge=0)
    cover_url: str = Field(default="", max_length=500)
    course_type: str = Field(default="single", pattern="^(intro|single|bundle)$")
    path_label: str = Field(default="", max_length=40)
    tagline: str = Field(default="", max_length=200)
    original_price: float | None = Field(default=None, ge=0)
    status: str = Field(default="on", pattern="^(on|off)$")
    sort_order: int = 0
    valid_days: int = Field(default=730, ge=0)
    trial_lesson_count: int = Field(default=1, ge=0)


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    semester: str | None = Field(default=None, max_length=40)
    teacher_id: int | None = None
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    cover_url: str | None = Field(default=None, max_length=500)
    course_type: str | None = Field(
        default=None, pattern="^(intro|single|bundle)$"
    )
    path_label: str | None = Field(default=None, max_length=40)
    tagline: str | None = Field(default=None, max_length=200)
    original_price: float | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(on|off)$")
    sort_order: int | None = None
    valid_days: int | None = Field(default=None, ge=0)
    trial_lesson_count: int | None = Field(default=None, ge=0)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    semester: str
    teacher_id: int | None
    teacher_name: str = ""
    description: str
    price: float = 2.99
    cover_url: str = ""
    enrolled: bool = False
    # 商城字段
    course_type: str = "single"
    path_label: str = ""
    tagline: str = ""
    original_price: float | None = None
    status: str = "on"
    sort_order: int = 0
    valid_days: int = 730
    trial_lesson_count: int = 1
    lesson_count: int = 0
    # 当前用户的学习权到期时间；为空且 enrolled=True 表示长期有效
    expires_at: datetime | None = None


class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int


class BundleItemsIn(BaseModel):
    """设置整包包含哪些单课（按给定顺序）。"""

    course_ids: list[int] = Field(default_factory=list, max_length=100)


class CoursePurchaseOut(BaseModel):
    id: int
    course_id: int
    course_name: str = ""
    amount: float
    channel: str = "mock"
    status: str = "paid"
    created_at: datetime
    course: CourseOut | None = None
    # 订单字段（兼容旧前端：全部有默认值）
    order_no: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    original_amount: float = 0.0
    discount_amount: float = 0.0
    order_type: str = "normal"
    transaction_id: str = ""
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    valid_until: datetime | None = None
    refund_amount: float = 0.0
    refunded_at: datetime | None = None
    refund_reason: str = ""


class ServiceProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="健康服务", max_length=40)
    description: str = ""
    price: float = Field(default=9.9, ge=0)
    cover_url: str = Field(default="", max_length=500)
    unit_label: str = Field(default="单次", max_length=40)
    tagline: str = Field(default="", max_length=200)
    original_price: float | None = Field(default=None, ge=0)
    status: str = Field(default="on", pattern="^(on|off)$")
    sort_order: int = 0
    valid_days: int = Field(default=365, ge=0)


class ServiceProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=40)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    cover_url: str | None = Field(default=None, max_length=500)
    unit_label: str | None = Field(default=None, max_length=40)
    tagline: str | None = Field(default=None, max_length=200)
    original_price: float | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(on|off)$")
    sort_order: int | None = None
    valid_days: int | None = Field(default=None, ge=0)


class ServiceProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: str
    price: float = 9.9
    cover_url: str = ""
    unit_label: str = "单次"
    owned: bool = False
    tagline: str = ""
    original_price: float | None = None
    status: str = "on"
    sort_order: int = 0
    valid_days: int = 365
    expires_at: datetime | None = None


class ServicePurchaseOut(BaseModel):
    id: int
    service_id: int
    service_name: str = ""
    amount: float
    channel: str = "mock"
    status: str = "paid"
    created_at: datetime
    service: ServiceProductOut | None = None
    order_no: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    original_amount: float = 0.0
    discount_amount: float = 0.0
    order_type: str = "normal"
    transaction_id: str = ""
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    valid_until: datetime | None = None
    refund_amount: float = 0.0
    refunded_at: datetime | None = None
    refund_reason: str = ""


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    due_at: datetime
    external_url: str = ""
    course_id: int | None = None
    # general / medication / oxygen / rehab / vitals / checkup / assessment / vaccine
    kind: str = Field(
        default="general",
        pattern="^(general|medication|oxygen|rehab|vitals|checkup|assessment|vaccine)$",
    )
    drug_name: str = Field(default="", max_length=120)
    dosage: str = Field(default="", max_length=120)
    repeat_rule: str = Field(default="none", pattern="^(none|daily|weekly)$")
    check_type: str = Field(default="", max_length=120)
    prep_questions: str = Field(default="", max_length=2000)


class ReminderUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    due_at: datetime | None = None
    external_url: str | None = None
    course_id: int | None = None
    kind: str | None = Field(
        default=None,
        pattern="^(general|medication|oxygen|rehab|vitals|checkup|assessment|vaccine)$",
    )
    drug_name: str | None = Field(default=None, max_length=120)
    dosage: str | None = Field(default=None, max_length=120)
    repeat_rule: str | None = Field(default=None, pattern="^(none|daily|weekly)$")
    check_type: str | None = Field(default=None, max_length=120)
    prep_questions: str | None = Field(default=None, max_length=2000)


class ReminderNotifyUpdate(BaseModel):
    enabled: bool


class ReminderDoneUpdate(BaseModel):
    completed: bool = True


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int | None = None
    course_name: str = ""
    title: str
    content: str
    due_at: datetime
    external_url: str
    creator_id: int
    # 管理员指定下发给某个用户的提醒；普通提醒为空
    target_user_id: int | None = None
    created_at: datetime
    status: str = "pending"  # pending / overdue
    source: str = "manager"  # user / manager / system
    notify_enabled: bool = True
    # 当前用户的完成状态（按人记录）
    completed: bool = False
    completed_at: datetime | None = None
    can_delete: bool = False
    can_edit: bool = False
    # 服务化提醒字段
    kind: str = "general"
    drug_name: str = ""
    dosage: str = ""
    repeat_rule: str = "none"
    check_type: str = ""
    prep_questions: str = ""
    recurring_parent_id: int | None = None


class NotificationOut(BaseModel):
    id: int
    user_id: int
    reminder_id: int
    course_id: int | None = None
    course_name: str = ""
    trigger_key: str = "due"
    title: str
    body: str = ""
    external_url: str = ""
    due_at: datetime | None = None
    created_at: datetime
    read_at: datetime | None = None
    read: bool = False
    # 点击通知时打开的前端路径
    click_url: str = ""


class NotificationListOut(BaseModel):
    items: list[NotificationOut] = Field(default_factory=list)
    total: int = 0
    unread: int = 0
    page: int = 1
    page_size: int = 20


class PushSubscriptionKeysIn(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=500)
    keys: PushSubscriptionKeysIn
    user_agent: str = Field(default="", max_length=300)


class PushUnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=500)


class ScheduleSlotCreate(BaseModel):
    course_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    location: str = ""


class ScheduleSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    course_name: str = ""
    weekday: int
    start_time: str
    end_time: str
    location: str


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    event_date: date
    description: str = ""


class CalendarEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    event_date: date
    description: str


class HomeOut(BaseModel):
    today_slots: list[ScheduleSlotOut]
    upcoming_reminders: list[ReminderOut]
    latest_notices: list[NoticeOut]
    upcoming_events: list[CalendarEventOut]
    unread_notifications: int = 0


class MaterialCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=2000)


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    course_name: str = ""
    title: str
    url: str = ""
    note: str = ""
    creator_id: int
    created_at: datetime
    can_delete: bool = False


class GradeCreate(BaseModel):
    course_id: int
    student_id: int
    title: str = Field(min_length=1, max_length=120)
    score: float = Field(ge=0, le=100)
    remark: str = Field(default="", max_length=200)


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    course_name: str = ""
    student_id: int
    student_name: str = ""
    title: str
    score: float
    remark: str = ""
    creator_id: int
    created_at: datetime
    can_delete: bool = False


class CommunityPostCreate(BaseModel):
    content: str = Field(default="", max_length=2000)
    image_urls: list[str] = Field(default_factory=list)


class CommunityRepostCreate(BaseModel):
    content: str = Field(default="", max_length=500)


class CommunityCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommunityImageOut(BaseModel):
    url: str


class CommunityCommentOut(BaseModel):
    id: int
    post_id: int
    author_id: int
    author_name: str = ""
    author_avatar_url: str = ""
    content: str
    created_at: datetime
    can_delete: bool = False


class CommunityOriginalOut(BaseModel):
    id: int
    author_name: str = ""
    content: str = ""
    image_urls: list[str] = Field(default_factory=list)


class CommunityPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    author_name: str = ""
    author_role: str = ""
    author_avatar_url: str = ""
    # 作者与当前用户的好友关系：self/none/pending_out/pending_in/friends
    author_friend_state: str = "none"
    content: str
    image_urls: list[str] = Field(default_factory=list)
    created_at: datetime
    can_delete: bool = False
    like_count: int = 0
    liked_by_me: bool = False
    comment_count: int = 0
    share_count: int = 0
    original_post_id: int | None = None
    original: CommunityOriginalOut | None = None


class FamilyLinkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    relation: str = Field(default="家人", max_length=40)
    phone: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=200)


class FamilyLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    relation: str
    phone: str = ""
    note: str = ""
    created_at: datetime


class HospitalLinkCreate(BaseModel):
    hospital_name: str = Field(min_length=1, max_length=120)
    department: str = Field(default="", max_length=80)
    doctor_name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=200)


class HospitalLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_name: str
    department: str = ""
    doctor_name: str = ""
    phone: str = ""
    address: str = ""
    note: str = ""
    created_at: datetime


# ---------- 管理员代办（routers/admin.py）----------


class AdminCourseGrant(BaseModel):
    course_id: int


class AdminServiceGrant(BaseModel):
    service_id: int


class AdminUserUpdate(BaseModel):
    """管理员改他人资料：不需要旧密码。"""

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    new_password: str | None = Field(default=None, min_length=4, max_length=100)


class AdminReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    due_at: datetime
    external_url: str = ""


class AdminReminderUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    due_at: datetime | None = None
    external_url: str | None = None


class AdminOverviewOut(BaseModel):
    user: UserOut
    courses: list[CourseOut] = Field(default_factory=list)
    services: list[ServiceProductOut] = Field(default_factory=list)
    reminders: list[ReminderOut] = Field(default_factory=list)


class ImpersonateIn(BaseModel):
    user_id: int


class ImpersonateOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- 好友（routers/friends.py）----------


class FriendRequestCreate(BaseModel):
    user_id: int


class FriendUserOut(BaseModel):
    """好友 / 申请人 / 搜索结果的统一用户视图。"""

    user_id: int
    username: str = ""
    full_name: str = ""
    role: str = ""
    avatar_url: str = ""
    # self/none/pending_out/pending_in/friends
    friend_state: str = "none"


class FriendOut(FriendUserOut):
    last_message: str = ""
    last_message_at: datetime | None = None
    unread_count: int = 0


class FriendRequestOut(FriendUserOut):
    request_id: int
    created_at: datetime
    # incoming = 待我处理，outgoing = 我发出的
    direction: str = "incoming"


class FriendRequestResultOut(BaseModel):
    request_id: int | None = None
    user_id: int
    status: str  # pending / accepted
    auto_accepted: bool = False


class FriendSummaryOut(BaseModel):
    pending_requests: int = 0
    unread_messages: int = 0
    total: int = 0


class FriendMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class FriendMessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    created_at: datetime
    mine: bool = False


# ---------- 商城：课时与学习进度（routers/courses.py）----------


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""
    video_url: str = Field(default="", max_length=500)
    duration_seconds: int = Field(default=0, ge=0)
    sort_order: int = 0
    is_trial: bool = False


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = None
    video_url: str | None = Field(default=None, max_length=500)
    duration_seconds: int | None = Field(default=None, ge=0)
    sort_order: int | None = None
    is_trial: bool | None = None


class LessonOut(BaseModel):
    id: int
    course_id: int
    title: str
    summary: str = ""
    video_url: str = ""
    duration_seconds: int = 0
    sort_order: int = 0
    is_trial: bool = False
    # 未购且非试看时为 True，此时 video_url 为空
    locked: bool = False


class CourseLessonsOut(BaseModel):
    course_id: int
    course_name: str
    owned: bool = False
    is_free: bool = False
    trial_lesson_count: int = 1
    total_lessons: int = 0
    completed_lessons: int = 0
    progress_percent: float = 0.0
    lessons: list[LessonOut] = Field(default_factory=list)


class LessonProgressIn(BaseModel):
    position_seconds: int = Field(default=0, ge=0)
    completed: bool | None = None


class LessonProgressOut(BaseModel):
    lesson_id: int
    course_id: int
    position_seconds: int = 0
    completed: bool = False
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class CourseProgressOut(BaseModel):
    course_id: int
    owned: bool = False
    total_lessons: int = 0
    completed_lessons: int = 0
    percent: float = 0.0
    # 退款校验用的「付费课时」进度（不含试看节）
    paid_total: int = 0
    paid_completed: int = 0
    paid_percent: float = 0.0
    lessons: list[LessonProgressOut] = Field(default_factory=list)


# ---------- 商城：商品、订单、退款（routers/mall.py）----------


# ---------- 板块测验（routers/courses.py）----------


class QuizQuestionOut(BaseModel):
    """下发给前端的题目：不带答案，防作弊。"""

    id: int
    question: str
    options: list[str] = Field(default_factory=list)


class QuizSubmitIn(BaseModel):
    # {题目id: 选择的选项下标}
    answers: dict[int, int] = Field(default_factory=dict)


class QuizDetailOut(BaseModel):
    question_id: int
    question: str
    chosen: int
    answer_index: int
    correct: bool
    explanation: str = ""
    # 错题可回看的课时；题库未关联课时时为空
    lesson_id: int | None = None
    lesson_title: str = ""


class QuizResultOut(BaseModel):
    course_id: int
    score: int
    total: int
    details: list[QuizDetailOut] = Field(default_factory=list)


class MallIncludedCourseOut(BaseModel):
    id: int
    name: str
    path_label: str = ""
    price: float = 0.0


class MallProductOut(BaseModel):
    # course / service
    product_type: str
    id: int
    name: str
    subtitle: str = ""
    description: str = ""
    price: float = 0.0
    original_price: float | None = None
    cover_url: str = ""
    category: str = ""
    unit_label: str = ""
    badge: str = ""
    # 仅课程：intro / single / bundle
    course_type: str = ""
    path_label: str = ""
    valid_days: int = 0
    lesson_count: int = 0
    trial_lesson_count: int = 0
    owned: bool = False
    expires_at: datetime | None = None
    sort_order: int = 0
    included_courses: list[MallIncludedCourseOut] = Field(default_factory=list)


class MallUpgradeQuoteOut(BaseModel):
    eligible: bool = False
    discount_amount: float = 0.0
    payable_amount: float = 0.0
    source_order_nos: list[str] = Field(default_factory=list)
    source_course_names: list[str] = Field(default_factory=list)
    message: str = ""


class MallProductDetailOut(MallProductOut):
    lessons: list[LessonOut] = Field(default_factory=list)
    upgrade_quote: MallUpgradeQuoteOut | None = None
    refund_policy: str = ""


class MallProductListOut(BaseModel):
    items: list[MallProductOut] = Field(default_factory=list)
    total: int = 0


class MallLearnerIn(BaseModel):
    user_id: int | None = None
    username: str | None = Field(default=None, max_length=64)
    name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=40)


class MallOrderCreate(BaseModel):
    product_type: str = Field(pattern="^(course|service)$")
    product_id: int
    quantity: int = Field(default=1, ge=1, le=200)
    channel: str = Field(default="mock", max_length=40)
    learners: list[MallLearnerIn] = Field(default_factory=list)
    remark: str = Field(default="", max_length=500)


class MallPayIn(BaseModel):
    channel: str = Field(default="mock", max_length=40)
    transaction_id: str = Field(default="", max_length=100)


class MallOrderSeatOut(BaseModel):
    id: int
    learner_user_id: int | None = None
    learner_name: str = ""
    learner_phone: str = ""
    activation_code: str = ""
    status: str = "pending"
    activated_at: datetime | None = None
    refund_amount: float = 0.0
    refunded_at: datetime | None = None


class MallOrderOut(BaseModel):
    id: int
    order_no: str
    product_type: str
    product_id: int
    product_name: str = ""
    product_cover: str = ""
    product_category: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    original_amount: float = 0.0
    discount_amount: float = 0.0
    amount: float = 0.0
    status: str = "pending"
    channel: str = "mock"
    order_type: str = "normal"
    transaction_id: str = ""
    buyer_id: int
    buyer_name: str = ""
    created_at: datetime
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    valid_until: datetime | None = None
    cancelled_at: datetime | None = None
    refunded_at: datetime | None = None
    refund_amount: float = 0.0
    refund_reason: str = ""
    upgrade_from_order_id: int | None = None
    upgrade_source_order_nos: list[str] = Field(default_factory=list)
    seats: list[MallOrderSeatOut] = Field(default_factory=list)
    can_pay: bool = False
    can_cancel: bool = False
    refundable: bool = False
    refund_hint: str = ""


class MallOrderListOut(BaseModel):
    items: list[MallOrderOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class MallRefundCheckOut(BaseModel):
    eligible: bool = False
    reason: str = ""
    refund_amount: float = 0.0
    within_window: bool = False
    window_ends_at: datetime | None = None
    progress_percent: float = 0.0
    policy: str = ""


class MallRefundIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class MallRedeemIn(BaseModel):
    activation_code: str = Field(min_length=1, max_length=40)


class MallRedeemOut(BaseModel):
    ok: bool = True
    course_id: int
    course_name: str = ""
    learner_name: str = ""
    expires_at: datetime | None = None


class MallMyCourseOut(BaseModel):
    course: CourseOut
    source: str = "purchase"
    expires_at: datetime | None = None
    total_lessons: int = 0
    completed_lessons: int = 0
    progress_percent: float = 0.0


class MallEntitlementsOut(BaseModel):
    courses: list[MallMyCourseOut] = Field(default_factory=list)
    services: list[ServiceProductOut] = Field(default_factory=list)


class MallSummaryOut(BaseModel):
    course_count: int = 0
    service_count: int = 0
    owned_course_count: int = 0
    owned_service_count: int = 0
    pending_orders: int = 0
    paid_orders: int = 0
    refund_policy: str = ""


class MallPaymentCallbackIn(BaseModel):
    order_no: str = Field(min_length=1, max_length=40)
    transaction_id: str = Field(default="", max_length=100)
    channel: str = Field(default="mock", max_length=40)
    status: str = Field(default="success", pattern="^(success|failed)$")


# ---------- 医院对接（只读） ----------


class HospitalPartnerOut(BaseModel):
    id: int
    code: str
    name: str
    department: str = ""
    status: str = "enabled"
    mode: str = "demo"
    contact: str = ""
    note: str = ""


class HospitalPartnerCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    department: str = Field(default="", max_length=80)
    mode: str = Field(default="demo", pattern="^(demo|http)$")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")
    contact: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=200)


class HospitalPartnerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    department: str | None = Field(default=None, max_length=80)
    mode: str | None = Field(default=None, pattern="^(demo|http)$")
    status: str | None = Field(default=None, pattern="^(enabled|disabled)$")
    contact: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=200)


class HospitalAuthorizationCreate(BaseModel):
    partner_id: int
    patient_ref: str = Field(min_length=4, max_length=120)
    # 必须由用户明确确认授权，避免误触
    consent: bool = False


class HospitalAuthorizationOut(BaseModel):
    id: int
    partner_id: int
    partner_name: str = ""
    patient_ref_masked: str = ""
    scopes: list[str] = Field(default_factory=list)
    status: str = "active"
    authorized_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class HospitalCaregiverCreate(BaseModel):
    caregiver_username: str = Field(min_length=1, max_length=64)
    relation: str = Field(default="照护者", max_length=40)


class HospitalCaregiverOut(BaseModel):
    id: int
    patient_user_id: int
    patient_name: str = ""
    caregiver_user_id: int
    caregiver_name: str = ""
    relation: str = "照护者"
    status: str = "active"
    granted_at: datetime
    revoked_at: datetime | None = None


class HospitalCaregiversOut(BaseModel):
    granted: list[HospitalCaregiverOut] = Field(default_factory=list)
    received: list[HospitalCaregiverOut] = Field(default_factory=list)


class HospitalRecordOut(BaseModel):
    id: int
    partner_id: int
    partner_name: str = ""
    record_type: str
    title: str
    content: str = ""
    doctor_name: str = ""
    department: str = ""
    occurred_at: datetime | None = None
    fetched_at: datetime


class HospitalSyncOut(BaseModel):
    added: int = 0
    updated: int = 0
    total: int = 0
    fetched_at: datetime


class HospitalReminderCreate(BaseModel):
    due_at: datetime
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=2000)


class HospitalReminderOut(BaseModel):
    reminder_id: int
    record_id: int
    title: str
    due_at: datetime


# ---------- AI 用药动作检测 ----------


class MedicationStepOut(BaseModel):
    name: str
    done: bool = False


class MedicationCheckOut(BaseModel):
    id: int
    user_id: int
    lesson_id: int | None = None
    status: str = "completed"
    provider: str = "demo"
    # oral=口服，inhale=吸入
    mode: str = "oral"
    steps: list[MedicationStepOut] = Field(default_factory=list)
    needs_retry: bool = False
    message: str = ""
    image_size: int = 0
    image_type: str = ""
    created_at: datetime
    expires_at: datetime | None = None
    disclaimer: str = ""


class MedicationCheckListOut(BaseModel):
    items: list[MedicationCheckOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    retention_days: int = 30
    disclaimer: str = ""


# ---------- 症状日记 ----------


class SymptomEntryIn(BaseModel):
    record_date: date | None = None
    cough: int = Field(default=0, ge=0, le=3)
    dyspnea: int = Field(default=0, ge=0, le=3)
    sputum: int = Field(default=0, ge=0, le=3)
    note: str = Field(default="", max_length=1000)


class SymptomEntryOut(BaseModel):
    id: int
    record_date: date
    cough: int = 0
    dyspnea: int = 0
    sputum: int = 0
    note: str = ""
    total: int = 0
    warning: bool = False
    warning_text: str = ""
    created_at: datetime
    updated_at: datetime


class SymptomDiaryOut(BaseModel):
    items: list[SymptomEntryOut] = Field(default_factory=list)
    warning: bool = False
    warning_text: str = ""
    disclaimer: str = ""


class HealthProfileIn(BaseModel):
    """个人健康档案写入：全部可选，允许只填一部分后逐步补全。"""

    sex: str = Field(default="", max_length=10)
    birth_year: str = Field(default="", max_length=10)
    height_cm: str = Field(default="", max_length=10)
    weight_kg: str = Field(default="", max_length=10)
    blood_type: str = Field(default="", max_length=10)

    diagnosis: str = Field(default="", max_length=120)
    diagnosed_at: str = Field(default="", max_length=20)
    copd_grade: str = Field(default="", max_length=20)
    fev1_percent: str = Field(default="", max_length=10)
    fev1_fvc: str = Field(default="", max_length=10)
    oxygen_target: str = Field(default="", max_length=30)

    current_meds: str = Field(default="", max_length=4000)
    allergies: str = Field(default="", max_length=2000)
    past_history: str = Field(default="", max_length=4000)

    emergency_name: str = Field(default="", max_length=60)
    emergency_relation: str = Field(default="", max_length=30)
    emergency_phone: str = Field(default="", max_length=40)

    doctor_name: str = Field(default="", max_length=60)
    doctor_hospital: str = Field(default="", max_length=120)
    doctor_dept: str = Field(default="", max_length=60)
    doctor_phone: str = Field(default="", max_length=40)

    notes: str = Field(default="", max_length=2000)


class HealthProfileOut(HealthProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    full_name: str = ""
    username: str = ""
    updated_at: datetime | None = None
    # 档案完整度（0-100）与缺失项提示，前端用来引导补全
    completeness: int = 0
    missing: list[str] = Field(default_factory=list)
