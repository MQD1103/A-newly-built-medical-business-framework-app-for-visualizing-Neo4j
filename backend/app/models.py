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

    teacher: Mapped[User | None] = relationship(back_populates="taught_courses")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="course")
    schedule_slots: Mapped[list["ScheduleSlot"]] = relationship(back_populates="course")
    materials: Mapped[list["CourseMaterial"]] = relationship(back_populates="course")
    grades: Mapped[list["Grade"]] = relationship(back_populates="course")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_enrollment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    student: Mapped[User] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")


class CoursePurchase(Base):
    """售课订单（当前为模拟支付成功记录）。"""

    __tablename__ = "course_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=2.99)
    # mock = 模拟支付
    channel: Mapped[str] = mapped_column(String(40), default="mock")
    status: Mapped[str] = mapped_column(String(20), default="paid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    course: Mapped[Course] = relationship()


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


class ServiceEntitlement(Base):
    """用户已开通的服务权益。"""

    __tablename__ = "service_entitlements"
    __table_args__ = (
        UniqueConstraint("user_id", "service_id", name="uq_service_entitlement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_products.id"), index=True)

    user: Mapped[User] = relationship()
    service: Mapped[ServiceProduct] = relationship()


class ServicePurchase(Base):
    """服务订单（模拟支付）。"""

    __tablename__ = "service_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_products.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=9.9)
    channel: Mapped[str] = mapped_column(String(40), default="mock")
    status: Mapped[str] = mapped_column(String(20), default="paid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
