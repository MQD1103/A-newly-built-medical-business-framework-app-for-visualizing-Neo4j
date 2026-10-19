from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), index=True)  # student/teacher/admin
    # 空字符串表示未自定义头像，登录页显示默认蓝球
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    taught_courses: Mapped[list["Course"]] = relationship(back_populates="teacher")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student")
    notices: Mapped[list["Notice"]] = relationship(back_populates="author")
    # reminders 到 users 有两条外键（creator_id / target_user_id），必须显式指定
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="creator", foreign_keys="Reminder.creator_id"
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    semester: Mapped[str] = mapped_column(String(40))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # 售课标价（元）
    price: Mapped[float] = mapped_column(Float, default=2.99)
    # 封面图，如 /uploads/courses/copd-1.svg
    cover_url: Mapped[str] = mapped_column(String(500), default="")
    # 商城课程类型：intro=免费入门，single=单路径/单课，bundle=整包
    course_type: Mapped[str] = mapped_column(String(20), default="single", index=True)
    # 展示用路径名，如「预防与预测」「患病管理」「整包」「免费入门」
    path_label: Mapped[str] = mapped_column(String(40), default="")
    # 列表/详情页的一句卖点
    tagline: Mapped[str] = mapped_column(String(200), default="")
    # 划线原价；为空表示不打折
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    # on=在售，off=下架（下架不影响已购用户学习）
    status: Mapped[str] = mapped_column(String(20), default="on", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # 购买后学习权有效期（天）；730 = 2 年
    valid_days: Mapped[int] = mapped_column(Integer, default=730)
    # 每个付费课程开放试看的节数（从第 1 节起）
    trial_lesson_count: Mapped[int] = mapped_column(Integer, default=1)

    teacher: Mapped[User | None] = relationship(back_populates="taught_courses")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="course")
    schedule_slots: Mapped[list["ScheduleSlot"]] = relationship(back_populates="course")
    materials: Mapped[list["CourseMaterial"]] = relationship(back_populates="course")
    grades: Mapped[list["Grade"]] = relationship(back_populates="course")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Lesson.sort_order",
    )
    bundle_items: Mapped[list["CourseBundleItem"]] = relationship(
        foreign_keys="CourseBundleItem.bundle_id",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="CourseBundleItem.sort_order",
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_enrollment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    # 该学习权来自哪一笔课程订单；管理员开通/种子数据可能为空
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_purchases.id"), nullable=True, index=True, default=None
    )
    # purchase=用户购买，bundle=整包开通时附带，admin=管理员开通，seed=演示数据
    source: Mapped[str] = mapped_column(String(20), default="purchase")
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # 为空表示长期有效（演示/管理员开通）；购买的是 paid_at + valid_days
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True, default=None
    )

    student: Mapped[User] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")


class CoursePurchase(Base):
    """课程订单（商城核心表；支付为模拟或回调确认）。

    状态机：pending → paid → refund_pending → refunded / partially_refunded；
            pending → cancelled / expired。
    amount 为应付金额（已扣升级差价），original_amount 为原价合计。
    """

    __tablename__ = "course_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    # 实付金额（元）
    amount: Mapped[float] = mapped_column(Float, default=2.99)
    # mock = 模拟支付；admin = 管理员开通（¥0 留痕）
    channel: Mapped[str] = mapped_column(String(40), default="mock")
    status: Mapped[str] = mapped_column(String(20), default="paid", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 商城订单字段
    order_no: Mapped[str] = mapped_column(String(40), default="", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    original_amount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    # normal=普通购买，upgrade=补差价升级为整包
    order_type: Mapped[str] = mapped_column(String(20), default="normal")
    upgrade_from_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 本订单已被哪笔升级订单抵扣；非空时不能重复用于补差价
    upgraded_to_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transaction_id: Mapped[str] = mapped_column(String(100), default="")
    # 学习权到期时间（paid_at + 课程 valid_days）
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 待支付订单的超时时间
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refund_reason: Mapped[str] = mapped_column(Text, default="")
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship()
    course: Mapped[Course] = relationship()
    seats: Mapped[list["CourseOrderSeat"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class ServiceProduct(Base):
    """商城可售服务商品（与底栏「服务」入口无关）。"""

    __tablename__ = "service_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), default="健康服务")
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float] = mapped_column(Float, default=9.9)
    cover_url: Mapped[str] = mapped_column(String(500), default="")
    # 如「单次」「30天」
    unit_label: Mapped[str] = mapped_column(String(40), default="单次")
    tagline: Mapped[str] = mapped_column(String(200), default="")
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(20), default="on", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # 服务权益有效期（天）；下单成功后写入权益到期时间
    valid_days: Mapped[int] = mapped_column(Integer, default=365)


class ServiceEntitlement(Base):
    """用户已开通的服务权益。"""

    __tablename__ = "service_entitlements"
    __table_args__ = (
        UniqueConstraint("user_id", "service_id", name="uq_service_entitlement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_products.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_purchases.id"), nullable=True, index=True, default=None
    )
    source: Mapped[str] = mapped_column(String(20), default="purchase")
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True, default=None
    )

    user: Mapped[User] = relationship()
    service: Mapped[ServiceProduct] = relationship()


class ServicePurchase(Base):
    """服务订单（状态机与课程订单一致）。"""

    __tablename__ = "service_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_products.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=9.9)
    channel: Mapped[str] = mapped_column(String(40), default="mock")
    status: Mapped[str] = mapped_column(String(20), default="paid", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order_no: Mapped[str] = mapped_column(String(40), default="", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    original_amount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    order_type: Mapped[str] = mapped_column(String(20), default="normal")
    transaction_id: Mapped[str] = mapped_column(String(100), default="")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refund_reason: Mapped[str] = mapped_column(Text, default="")
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship()
    service: Mapped[ServiceProduct] = relationship()


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    # all / student / teacher
    audience: Mapped[str] = mapped_column(String(20), default="all")
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    author: Mapped[User] = relationship(back_populates="notices")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id"), nullable=True, index=True, default=None
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")  # 说明（可选）
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    external_url: Mapped[str] = mapped_column(String(500), default="")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # 管理员为指定用户下发的提醒；空表示按课程/创建者可见性推导
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True, default=None
    )
    # user=个人添加；manager=教师/管理员；system=系统种子
    source: Mapped[str] = mapped_column(String(20), default="manager", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course: Mapped[Course] = relationship(back_populates="reminders")
    creator: Mapped[User] = relationship(
        back_populates="reminders", foreign_keys=[creator_id]
    )
    prefs: Mapped[list["ReminderPreference"]] = relationship(back_populates="reminder")


class ReminderPreference(Base):
    """用户对管理者/系统提醒的「是否提醒」开关（不能删除那些提醒）。"""

    __tablename__ = "reminder_prefs"
    __table_args__ = (UniqueConstraint("user_id", "reminder_id", name="uq_reminder_pref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    reminder: Mapped[Reminder] = relationship(back_populates="prefs")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0=周一 ... 6=周日
    start_time: Mapped[str] = mapped_column(String(8))  # HH:MM
    end_time: Mapped[str] = mapped_column(String(8))
    location: Mapped[str] = mapped_column(String(120), default="")

    course: Mapped[Course] = relationship(back_populates="schedule_slots")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class CommunityPost(Base):
    """社区动态；original_post_id 非空表示为转发。"""

    __tablename__ = "community_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    # JSON 数组字符串，如 ["/uploads/community/a.jpg"]
    image_urls: Mapped[str] = mapped_column(Text, default="[]")
    original_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("community_posts.id"), nullable=True, index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    author: Mapped[User] = relationship()
    original: Mapped["CommunityPost | None"] = relationship(
        remote_side=[id], foreign_keys=[original_post_id]
    )
    likes: Mapped[list["CommunityLike"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    comments: Mapped[list["CommunityComment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class CommunityLike(Base):
    __tablename__ = "community_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_community_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("community_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    post: Mapped[CommunityPost] = relationship(back_populates="likes")
    user: Mapped[User] = relationship()


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("community_posts.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    post: Mapped[CommunityPost] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()


class CourseMaterial(Base):
    """课程资料（链接/说明，轻量，非完整网盘）。"""

    __tablename__ = "course_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course: Mapped[Course] = relationship(back_populates="materials")
    creator: Mapped[User] = relationship()


class Grade(Base):
    """成绩条目（考核项分数）。"""

    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))  # 如 平时 / 期中 / 期末
    score: Mapped[float] = mapped_column(Float)
    remark: Mapped[str] = mapped_column(String(200), default="")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course: Mapped[Course] = relationship(back_populates="grades")
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])


class FamilyLink(Base):
    """家人关联（紧急联系 / 陪护信息）。"""

    __tablename__ = "family_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    relation: Mapped[str] = mapped_column(String(40), default="家人")  # 配偶/子女/父母等
    phone: Mapped[str] = mapped_column(String(40), default="")
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()


class HospitalLink(Base):
    """医院 / 科室关联。"""

    __tablename__ = "hospital_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hospital_name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(80), default="")
    doctor_name: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()


class FriendRequest(Base):
    """好友关系：一行代表一对用户。

    pending = 待对方验证，accepted = 已是好友。
    用 user_low_id < user_high_id 的规范化写法，配合唯一约束保证
    「同一对用户只有一行」，方向由 requester_id 表达。
    """

    __tablename__ = "friend_requests"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_friend_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 规范化的一对用户：low < high
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 发起方（low / high 之一），决定申请出现在谁的「待处理」里
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # 同意时间（含反向申请时的自动同意）；删除好友整行删掉
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )


class FriendMessage(Base):
    """好友私信。read_at 为空表示收件人未读（用于未读红点）。"""

    __tablename__ = "friend_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, index=True
    )


# ---------- 商城：整包、课时、学习进度、团购名额 ----------


class CourseBundleItem(Base):
    """整包课程包含哪些单课。"""

    __tablename__ = "course_bundle_items"
    __table_args__ = (
        UniqueConstraint("bundle_id", "course_id", name="uq_bundle_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    bundle: Mapped[Course] = relationship(
        back_populates="bundle_items", foreign_keys=[bundle_id]
    )
    course: Mapped[Course] = relationship(foreign_keys=[course_id])


class Lesson(Base):
    """课程章节（录播）。is_trial=True 表示未购用户也可完整试看。"""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    video_url: Mapped[str] = mapped_column(String(500), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course: Mapped[Course] = relationship(back_populates="lessons")


class LessonProgress(Base):
    """用户课时学习进度（续播位置 + 是否完成）。"""

    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    position_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship()
    lesson: Mapped[Lesson] = relationship()


class CourseOrderSeat(Base):
    """课程订单的学习名额。

    普通购课：一条名额，学习人是买家本人。
    团购/代买：一条订单多条名额，可先绑定用户，也可先拿激活码后兑换。
    """

    __tablename__ = "course_order_seats"
    __table_args__ = (
        UniqueConstraint("activation_code", name="uq_seat_activation_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("course_purchases.id"), index=True)
    learner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True, default=None
    )
    learner_name: Mapped[str] = mapped_column(String(100), default="")
    learner_phone: Mapped[str] = mapped_column(String(40), default="")
    # 未指定学习人时，把激活码发给学习者，由其登录后兑换
    activation_code: Mapped[str] = mapped_column(String(40), index=True)
    # pending=待激活/待兑换，activated=已开通，refunded=已退
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped[CoursePurchase] = relationship(back_populates="seats")
    learner: Mapped[User | None] = relationship()


class ReminderCompletion(Base):
    """用户对某条提醒的完成状态（按人记录，互不影响）。"""

    __tablename__ = "reminder_completions"
    __table_args__ = (
        UniqueConstraint("user_id", "reminder_id", name="uq_reminder_completion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminders.id"), index=True
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    reminder: Mapped[Reminder] = relationship()


class Notification(Base):
    """站内通知，同时作为提醒的触发记录。

    同一个 (用户, 提醒, 触发档位) 只会生成一条，保证定时任务重复执行不重复打扰。
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "reminder_id",
            "trigger_key",
            name="uq_notification_trigger",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminders.id"), index=True
    )
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id"), nullable=True, default=None
    )
    # 触发档位：7d=提前 7 天，1d=提前 1 天，due=到期/已过期
    trigger_key: Mapped[str] = mapped_column(String(20), default="due")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    external_url: Mapped[str] = mapped_column(String(500), default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    reminder: Mapped[Reminder] = relationship()
    course: Mapped[Course | None] = relationship()


class HospitalPartner(Base):
    """已开通的合作医院。

    mode=demo 时由内置演示数据提供只读记录；mode=http 时通过
    HOSPITAL_API_BASE_URL 指向的医院接口拉取。真实地址和 Token 只放环境变量。
    """

    __tablename__ = "hospital_partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(20), default="enabled", index=True)
    mode: Mapped[str] = mapped_column(String(20), default="demo")
    contact: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HospitalAuthorization(Base):
    """用户对合作医院的授权状态；撤销后保留记录便于追溯。"""

    __tablename__ = "hospital_authorizations"
    __table_args__ = (
        UniqueConstraint("user_id", "partner_id", name="uq_hospital_auth_user_partner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("hospital_partners.id"), index=True)
    # 医院侧患者标识：仅用于拉取数据，列表接口只返回脱敏值
    patient_ref: Mapped[str] = mapped_column(String(120))
    scopes: Mapped[str] = mapped_column(String(200), default="advice,condition,record")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    authorized_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    partner: Mapped[HospitalPartner] = relationship()


class HospitalRecord(Base):
    """医院嘱托 / 病情说明 / 病历摘要的只读缓存。

    仅缓存授权范围内的内容；不提供任何修改、开药接口。
    """

    __tablename__ = "hospital_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "partner_id", "external_id",
            name="uq_hospital_record_external",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("hospital_partners.id"), index=True)
    # advice=医生嘱托，condition=病情说明，record=病历/检查摘要
    record_type: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    doctor_name: Mapped[str] = mapped_column(String(80), default="")
    department: Mapped[str] = mapped_column(String(80), default="")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    partner: Mapped[HospitalPartner] = relationship()


class HospitalCaregiverGrant(Base):
    """患者授权某位已注册用户查看自己的医院只读资料。"""

    __tablename__ = "hospital_caregiver_grants"
    __table_args__ = (
        UniqueConstraint(
            "patient_user_id", "caregiver_user_id",
            name="uq_hospital_caregiver_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    caregiver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    relation: Mapped[str] = mapped_column(String(40), default="照护者")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped[User] = relationship(foreign_keys=[patient_user_id])
    caregiver: Mapped[User] = relationship(foreign_keys=[caregiver_user_id])


class HospitalReminderLink(Base):
    """由医院嘱托生成提醒时留下的来源记录（不修改 reminders 表结构）。"""

    __tablename__ = "hospital_reminder_links"
    __table_args__ = (
        UniqueConstraint("reminder_id", name="uq_hospital_reminder_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("hospital_records.id"), index=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    record: Mapped[HospitalRecord] = relationship()
    reminder: Mapped[Reminder] = relationship()


class MedicationCheck(Base):
    """AI 用药动作检测的结果摘要。

    只保存「步骤是否完成 / 是否需要重做」类摘要，不保存原始影像，也不保存
    药效或诊断结论。记录按保留天数自动清理，且仅本人可查。
    """

    __tablename__ = "medication_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id"), nullable=True, index=True, default=None
    )
    # completed=检测完成；failed=检测服务异常，仅保留错误摘要
    status: Mapped[str] = mapped_column(String(20), default="completed", index=True)
    provider: Mapped[str] = mapped_column(String(20), default="demo")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    needs_retry: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(String(500), default="")
    # 仅记录体积与类型用于排障，不保存图片内容
    image_size: Mapped[int] = mapped_column(Integer, default=0)
    image_type: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()
    lesson: Mapped[Lesson | None] = relationship()
