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


class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int


class CoursePurchaseOut(BaseModel):
    id: int
    course_id: int
    course_name: str = ""
    amount: float
    channel: str = "mock"
    status: str = "paid"
    created_at: datetime
    course: CourseOut | None = None


class ServiceProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="健康服务", max_length=40)
    description: str = ""
    price: float = Field(default=9.9, ge=0)
    cover_url: str = Field(default="", max_length=500)
    unit_label: str = Field(default="单次", max_length=40)


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


class ServicePurchaseOut(BaseModel):
    id: int
    service_id: int
    service_name: str = ""
    amount: float
    channel: str = "mock"
    status: str = "paid"
    created_at: datetime
    service: ServiceProductOut | None = None


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    due_at: datetime
    external_url: str = ""
    course_id: int | None = None


class ReminderUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    due_at: datetime | None = None
    external_url: str | None = None
    course_id: int | None = None


class ReminderNotifyUpdate(BaseModel):
    enabled: bool


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
    created_at: datetime
    status: str = "pending"  # pending / overdue
    source: str = "manager"  # user / manager / system
    notify_enabled: bool = True
    can_delete: bool = False
    can_edit: bool = False


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
