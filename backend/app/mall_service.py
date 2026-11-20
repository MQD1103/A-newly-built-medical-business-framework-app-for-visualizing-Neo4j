"""商城业务核心：商品可见性、学习权、订单状态机、退款与团购名额。

设计要点
--------
- 学习权仍落在 Enrollment 表：整包只给「整包课程」写一条 Enrollment，
  包内单课的访问权由 CourseBundleItem 推导，退款时删除整包 Enrollment 即可，
  不会误删用户此前单独购买的单课。
- 订单沿用 CoursePurchase / ServicePurchase 两张表，补商城字段，
  保留旧接口与旧数据可用。
- 金额一律保留两位小数；时间是本地（UTC，与项目既有写法一致）naive datetime。
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import (
    Course,
    CourseBundleItem,
    CourseOrderSeat,
    CoursePurchase,
    Enrollment,
    Lesson,
    LessonProgress,
    ServiceEntitlement,
    ServiceProduct,
    ServicePurchase,
    User,
)
from .schemas import (
    MallIncludedCourseOut,
    MallOrderOut,
    MallOrderSeatOut,
    MallProductDetailOut,
    MallProductOut,
    MallUpgradeQuoteOut,
    LessonOut,
)

ORDER_TTL_MINUTES = 15
REFUND_WINDOW_DAYS = 7
REFUND_PROGRESS_LIMIT = 20.0  # 百分比
MAX_GROUP_QUANTITY = 200
# 学习权剩余天数 ≤ 该值时，前端提示「即将到期，可续期」
EXPIRING_SOON_DAYS = 30

REFUND_POLICY = (
    "购买后 7 天内且付费课时完成进度低于 20%，可申请全额退款；"
    "超过 7 天或进度达到 20% 不再退款。团购未激活名额可按未开通部分退款。"
)

COURSE_TYPE_LABEL = {
    "intro": "免费入门",
    "single": "单课",
    "bundle": "整包",
}


class MallError(Exception):
    """带 HTTP 状态码的业务错误，由路由层转成 HTTPException。"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def now() -> datetime:
    return datetime.utcnow()


def money(value: float | None) -> float:
    return round(float(value or 0), 2)


def valid_days_label(days: int) -> str:
    days = int(days or 0)
    if days <= 0:
        return "长期有效"
    if days % 365 == 0:
        return f"{days // 365}年"
    if days % 30 == 0:
        return f"{days // 30}天"
    return f"{days}天"


def gen_order_no(prefix: str) -> str:
    return (
        f"{prefix}{datetime.utcnow():%Y%m%d%H%M%S}"
        f"{secrets.randbelow(1_000_000):06d}"
    )


def gen_activation_code(db: Session) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(12))
        exists = (
            db.query(CourseOrderSeat.id)
            .filter(CourseOrderSeat.activation_code == code)
            .first()
        )
        if not exists:
            return code


def unique_order_no(db: Session, prefix: str) -> str:
    model = CoursePurchase if prefix == "C" else ServicePurchase
    column = model.order_no
    for _ in range(8):
        candidate = gen_order_no(prefix)
        if not db.query(model.id).filter(column == candidate).first():
            return candidate
    raise MallError("生成订单号失败，请重试", 500)


# ---------- 课程访问权 ----------


def course_is_free(course: Course) -> bool:
    return course.course_type == "intro" or float(course.price or 0) <= 0


def order_course(db: Session, order: CoursePurchase) -> Course | None:
    return db.get(Course, order.course_id)


def bundle_course_ids(db: Session, bundle_id: int) -> list[int]:
    rows = (
        db.query(CourseBundleItem.course_id)
        .filter(CourseBundleItem.bundle_id == bundle_id)
        .order_by(CourseBundleItem.sort_order, CourseBundleItem.id)
        .all()
    )
    return [int(r[0]) for r in rows]


def course_lesson_scope_ids(db: Session, course: Course) -> list[int]:
    """课程本身 + 整包内单课的 id，用于课时与进度统计。"""
    ids = [course.id]
    if course.course_type == "bundle":
        ids.extend(bundle_course_ids(db, course.id))
    return ids


def active_enrollment(db: Session, user_id: int, course_id: int) -> Enrollment | None:
    current = now()
    return (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == user_id,
            Enrollment.course_id == course_id,
            or_(Enrollment.expires_at.is_(None), Enrollment.expires_at > current),
        )
        .first()
    )


def course_access_info(
    db: Session, user: User, course: Course
) -> tuple[bool, datetime | None, str]:
    """返回 (是否可学, 到期时间, 来源)。"""
    if user.role == "admin":
        return True, None, "admin"
    if course_is_free(course):
        return True, None, "free"
    if user.role == "teacher" and course.teacher_id == user.id:
        return True, None, "teacher"

    direct = active_enrollment(db, user.id, course.id)
    if direct:
        return True, direct.expires_at, direct.source

    # 整包带来的单课访问权
    current = now()
    rows = (
        db.query(Enrollment)
        .join(CourseBundleItem, CourseBundleItem.bundle_id == Enrollment.course_id)
        .filter(
            Enrollment.student_id == user.id,
            CourseBundleItem.course_id == course.id,
            or_(Enrollment.expires_at.is_(None), Enrollment.expires_at > current),
        )
        .all()
    )
    if rows:
        permanent = any(r.expires_at is None for r in rows)
        latest = max((r.expires_at for r in rows if r.expires_at), default=None)
        return True, (None if permanent else latest), "bundle"
    return False, None, ""


def has_course_access(db: Session, user: User, course: Course) -> bool:
    return course_access_info(db, user, course)[0]


def days_left(expires_at: datetime | None, current: datetime | None = None) -> int | None:
    """学习权剩余天数（不足一天按一天算）；长期有效返回 None。"""
    if expires_at is None:
        return None
    current = current or now()
    seconds = (expires_at - current).total_seconds()
    if seconds <= 0:
        return 0
    return int(-(-seconds // 86400))


def enrollment_expiry_map(db: Session, user_id: int) -> dict[int, dict]:
    """一次查出该用户全部学习权（含已过期），供课程列表判定有效期状态。

    返回 {course_id: {"expires_at": datetime|None, "expired": bool}}：
    - 长期有效（expires_at 为空）优先，其次取最晚到期时间；
    - 全为已过期记录时 expired=True，前端显示「已过期·可续期」。
    """
    rows = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == user_id)
        .all()
    )
    current = now()
    result: dict[int, dict] = {}
    for row in rows:
        item = result.setdefault(
            row.course_id, {"expires_at": None, "permanent": False, "expired": True}
        )
        if row.expires_at is None:
            item["permanent"] = True
            item["expired"] = False
            continue
        if row.expires_at > current:
            item["expired"] = False
            if item["expires_at"] is None or row.expires_at > item["expires_at"]:
                item["expires_at"] = row.expires_at
    for item in result.values():
        if item["permanent"]:
            item["expires_at"] = None
    return result


def accessible_course_ids(db: Session, user: User) -> set[int]:
    if user.role == "admin":
        return {int(r[0]) for r in db.query(Course.id).all()}

    ids = {
        int(r[0])
        for r in db.query(Course.id)
        .filter(or_(Course.course_type == "intro", Course.price <= 0))
        .all()
    }
    if user.role == "teacher":
        ids |= {
            int(r[0])
            for r in db.query(Course.id).filter(Course.teacher_id == user.id).all()
        }

    current = now()
    direct = (
        db.query(Enrollment.course_id)
        .filter(
            Enrollment.student_id == user.id,
            or_(Enrollment.expires_at.is_(None), Enrollment.expires_at > current),
        )
        .all()
    )
    direct_ids = {int(r[0]) for r in direct}
    ids |= direct_ids

    bundle_ids = [
        int(r[0])
        for r in db.query(Course.id)
        .filter(Course.id.in_(direct_ids), Course.course_type == "bundle")
        .all()
    ]
    if bundle_ids:
        ids |= {
            int(r[0])
            for r in db.query(CourseBundleItem.course_id)
            .filter(CourseBundleItem.bundle_id.in_(bundle_ids))
            .all()
        }
    return ids


# ---------- 服务访问权 ----------


def active_service_entitlement(
    db: Session, user_id: int, service_id: int
) -> ServiceEntitlement | None:
    current = now()
    return (
        db.query(ServiceEntitlement)
        .filter(
            ServiceEntitlement.user_id == user_id,
            ServiceEntitlement.service_id == service_id,
            or_(
                ServiceEntitlement.expires_at.is_(None),
                ServiceEntitlement.expires_at > current,
            ),
        )
        .first()
    )


def service_access_info(
    db: Session, user: User, service: ServiceProduct
) -> tuple[bool, datetime | None, str]:
    if user.role == "admin":
        return True, None, "admin"
    ent = active_service_entitlement(db, user.id, service.id)
    if ent:
        return True, ent.expires_at, ent.source
    return False, None, ""


def has_service_access(db: Session, user: User, service: ServiceProduct) -> bool:
    return service_access_info(db, user, service)[0]


def accessible_service_ids(db: Session, user: User) -> set[int]:
    if user.role == "admin":
        return {int(r[0]) for r in db.query(ServiceProduct.id).all()}
    current = now()
    return {
        int(r[0])
        for r in db.query(ServiceEntitlement.service_id)
        .filter(
            ServiceEntitlement.user_id == user.id,
            or_(
                ServiceEntitlement.expires_at.is_(None),
                ServiceEntitlement.expires_at > current,
            ),
        )
        .all()
    }


# ---------- 课时与进度 ----------


def course_lessons(db: Session, course: Course) -> list[Lesson]:
    scope = course_lesson_scope_ids(db, course)
    return (
        db.query(Lesson)
        .filter(Lesson.course_id.in_(scope))
        .order_by(Lesson.course_id, Lesson.sort_order, Lesson.id)
        .all()
    )


def lesson_is_unlocked(course: Course, lesson: Lesson, owned: bool) -> bool:
    if owned or course_is_free(course):
        return True
    if lesson.is_trial:
        return True
    return lesson.sort_order < max(int(course.trial_lesson_count or 0), 0)


def lesson_outs(db: Session, course: Course, user: User) -> list[LessonOut]:
    owned = has_course_access(db, user, course)
    scope = course_lesson_scope_ids(db, course)
    rows = (
        db.query(Lesson)
        .filter(Lesson.course_id.in_(scope))
        .order_by(Lesson.course_id, Lesson.sort_order, Lesson.id)
        .all()
    )
    result: list[LessonOut] = []
    for lesson in rows:
        # 试看节数是对每门课分别计算的；整包内单课各放开自己的第 1 节
        lesson_course = lesson.course
        unlocked = owned or lesson_is_unlocked(lesson_course, lesson, False)
        result.append(
            LessonOut(
                id=lesson.id,
                course_id=lesson.course_id,
                title=lesson.title,
                summary=lesson.summary or "",
                video_url=(lesson.video_url or "") if unlocked else "",
                duration_seconds=int(lesson.duration_seconds or 0),
                sort_order=int(lesson.sort_order or 0),
                is_trial=bool(lesson.is_trial),
                locked=not unlocked,
            )
        )
    return result


def course_progress(db: Session, user_id: int, course: Course) -> dict:
    lessons = course_lessons(db, course)
    lesson_ids = [lesson.id for lesson in lessons]
    paid_ids = [lesson.id for lesson in lessons if not lesson.is_trial]

    completed: set[int] = set()
    if lesson_ids:
        completed = {
            int(r[0])
            for r in db.query(LessonProgress.lesson_id)
            .filter(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id.in_(lesson_ids),
                LessonProgress.completed.is_(True),
            )
            .all()
        }

    total = len(lessons)
    paid_total = len(paid_ids)
    done = len(completed)
    paid_done = len([lesson_id for lesson_id in paid_ids if lesson_id in completed])
    return {
        "total_lessons": total,
        "completed_lessons": done,
        "percent": round(done * 100.0 / total, 1) if total else 0.0,
        "paid_total": paid_total,
        "paid_completed": paid_done,
        "paid_percent": round(paid_done * 100.0 / paid_total, 1) if paid_total else 0.0,
    }


def order_progress_percent(db: Session, order: CoursePurchase, user_id: int) -> float:
    course = order_course(db, order)
    if not course:
        return 0.0
    return float(course_progress(db, user_id, course)["paid_percent"])


# ---------- 开通 / 收回 ----------


def grant_course_enrollment(
    db: Session,
    user_id: int,
    course_id: int,
    order: CoursePurchase | None,
    source: str,
    expires_at: datetime | None,
) -> Enrollment:
    current = now()
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == user_id,
            Enrollment.course_id == course_id,
        )
        .first()
    )
    if enrollment is None:
        enrollment = Enrollment(
            student_id=user_id,
            course_id=course_id,
            order_id=order.id if order else None,
            source=source,
            granted_at=current,
            expires_at=expires_at,
        )
        db.add(enrollment)
        return enrollment

    # 长期有效（管理员开通/演示数据）不被短期购买覆盖
    if enrollment.expires_at is None:
        return enrollment
    # 已过期、或本次到期时间更晚（续期/重购）时刷新。
    # 续期叠加在 pay_course_order 里按「剩余有效期 + 本次时长」算好，这里直接落库。
    if enrollment.expires_at <= current or (
        expires_at is not None and expires_at > enrollment.expires_at
    ):
        enrollment.order_id = order.id if order else enrollment.order_id
        enrollment.source = source
        enrollment.granted_at = current
        enrollment.expires_at = expires_at
    return enrollment


def grant_service_entitlement(
    db: Session,
    user_id: int,
    service_id: int,
    order: ServicePurchase | None,
    source: str,
    expires_at: datetime | None,
) -> ServiceEntitlement:
    current = now()
    entitlement = (
        db.query(ServiceEntitlement)
        .filter(
            ServiceEntitlement.user_id == user_id,
            ServiceEntitlement.service_id == service_id,
        )
        .first()
    )
    if entitlement is None:
        entitlement = ServiceEntitlement(
            user_id=user_id,
            service_id=service_id,
            order_id=order.id if order else None,
            source=source,
            granted_at=current,
            expires_at=expires_at,
        )
        db.add(entitlement)
        return entitlement
    if entitlement.expires_at is None:
        return entitlement
    if entitlement.expires_at <= current or (
        expires_at is not None and expires_at > entitlement.expires_at
    ):
        entitlement.order_id = order.id if order else entitlement.order_id
        entitlement.source = source
        entitlement.granted_at = current
        entitlement.expires_at = expires_at
    return entitlement


def revoke_order_entitlements(db: Session, order: CoursePurchase) -> None:
    db.query(Enrollment).filter(
        Enrollment.order_id == order.id,
        Enrollment.course_id == order.course_id,
    ).delete(synchronize_session=False)


# ---------- 升级抵扣 ----------


def _upgrade_source_amount(db: Session, user: User, order: CoursePurchase) -> float:
    """一笔单课订单能给升级抵扣多少：只认买家本人真正在学的份额。"""
    if order.seats:
        own_seat = any(
            seat.learner_user_id == user.id and seat.status == "activated"
            for seat in order.seats
        )
        if not own_seat:
            return 0.0
        if int(order.quantity or 1) > 1:
            return money(order.unit_price)
        return money(
            float(order.amount or 0) - float(order.refund_amount or 0)
        )
    # 历史订单没有名额记录，按买家本人购买处理
    return money(float(order.amount or 0) - float(order.refund_amount or 0))


def upgrade_quote(db: Session, user: User, bundle: Course) -> dict:
    """已购单课补差价升级为整包：按已实付金额抵扣整包价。"""
    if bundle.course_type != "bundle":
        return {"eligible": False, "orders": [], "discount": 0.0, "payable": 0.0}

    included_ids = bundle_course_ids(db, bundle.id)
    if not included_ids:
        return {"eligible": False, "orders": [], "discount": 0.0, "payable": 0.0}

    rows = (
        db.query(CoursePurchase)
        .filter(
            CoursePurchase.user_id == user.id,
            CoursePurchase.status.in_(["paid", "partially_refunded"]),
            CoursePurchase.course_id.in_(included_ids),
            CoursePurchase.upgraded_to_order_id.is_(None),
        )
        .order_by(CoursePurchase.paid_at.desc(), CoursePurchase.id.desc())
        .all()
    )
    # 同一门课可能因到期后重购产生多条，只取最近一笔
    latest: dict[int, CoursePurchase] = {}
    for row in rows:
        latest.setdefault(row.course_id, row)
    orders = [row for row in latest.values() if _upgrade_source_amount(db, user, row) > 0]
    discount = money(
        sum(_upgrade_source_amount(db, user, order) for order in orders)
    )
    price = money(bundle.price)
    discount = money(min(discount, price))
    return {
        "eligible": bool(orders),
        "orders": orders,
        "discount": discount,
        "payable": money(max(price - discount, 0)),
    }


def upgrade_quote_out(db: Session, user: User, bundle: Course) -> MallUpgradeQuoteOut:
    quote = upgrade_quote(db, user, bundle)
    sources: list[CoursePurchase] = quote["orders"]
    names = []
    for order in sources:
        course = order_course(db, order)
        if course:
            names.append(course.name)
    if not quote["eligible"]:
        message = "未拥有整包内课程，可按整包价直接购买"
    elif quote["payable"] <= 0:
        message = "已拥有整包全部课程，无需再次购买"
    else:
        message = f"已购课程可抵扣 ¥{quote['discount']:.2f}"
    return MallUpgradeQuoteOut(
        eligible=bool(quote["eligible"]),
        discount_amount=money(quote["discount"]),
        payable_amount=money(quote["payable"]),
        source_order_nos=[order.order_no for order in sources],
        source_course_names=names,
        message=message,
    )


# ---------- 下单 ----------


def _resolve_learner(db: Session, item) -> User | None:
    if item.user_id:
        learner = db.get(User, int(item.user_id))
        if not learner:
            raise MallError(f"学习者用户 {item.user_id} 不存在", 400)
        return learner
    if item.username:
        learner = db.query(User).filter(User.username == item.username.strip()).first()
        if not learner:
            raise MallError(f"学习者账号 {item.username} 不存在", 400)
        return learner
    return None


def _build_seats(
    db: Session,
    order: CoursePurchase,
    buyer: User,
    quantity: int,
    learners: list,
) -> None:
    if len(learners) > quantity:
        raise MallError("学习者人数超过购买名额数", 400)

    seen: set[int] = set()
    for item in learners:
        learner = _resolve_learner(db, item)
        if learner is not None:
            if learner.id in seen:
                raise MallError("同一学习者不能占用多个名额", 400)
            seen.add(learner.id)
            if has_course_access(db, learner, order.course):
                raise MallError(
                    f"学习者「{learner.full_name or learner.username}」已拥有该课程", 400
                )
        db.add(
            CourseOrderSeat(
                order_id=order.id,
                learner_user_id=learner.id if learner else None,
                learner_name=(item.name or (learner.full_name if learner else "")).strip(),
                learner_phone=(item.phone or "").strip(),
                activation_code=gen_activation_code(db),
                status="pending",
            )
        )

    remaining = quantity - len(learners)
    if remaining > 0 and quantity == 1 and not learners:
        # 普通自助购买：买的人就是学的人
        db.add(
            CourseOrderSeat(
                order_id=order.id,
                learner_user_id=buyer.id,
                learner_name=buyer.full_name,
                learner_phone="",
                activation_code=gen_activation_code(db),
                status="pending",
            )
        )
        return
    for _ in range(remaining):
        db.add(
            CourseOrderSeat(
                order_id=order.id,
                learner_user_id=None,
                learner_name="",
                learner_phone="",
                activation_code=gen_activation_code(db),
                status="pending",
            )
        )


def create_course_order(
    db: Session,
    user: User,
    product_id: int,
    quantity: int = 1,
    channel: str = "mock",
    learners: list | None = None,
    remark: str = "",
    renew: bool = False,
) -> CoursePurchase:
    course = db.get(Course, product_id)
    if not course:
        raise MallError("课程不存在", 404)
    if user.role == "admin":
        raise MallError("管理员无需购买，已默认可查看全部课程", 400)
    if (course.status or "on") != "on":
        raise MallError("该课程已下架", 409)
    if course_is_free(course):
        raise MallError("免费课程无需下单，登录后可直接学习", 400)

    access, _, access_source = course_access_info(db, user, course)
    # 该课的直接学习权是否来自购买（用来判断能不能续期：过期后同样可以续期）
    direct = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == user.id,
            Enrollment.course_id == course.id,
        )
        .first()
    )
    can_renew = bool(
        direct
        and (direct.source or "") == "purchase"
        and int(course.valid_days or 0) > 0
        and (not access or access_source == "purchase")
    )
    if access and not renew:
        raise MallError("已拥有该课程，无需重复购买", 409)
    if renew and not can_renew:
        raise MallError("当前学习权不支持续期（长期有效或由整包开通）", 409)
    if renew and quantity > 1:
        raise MallError("续期一次只能续一门课程", 400)
    if quantity < 1 or quantity > MAX_GROUP_QUANTITY:
        raise MallError(f"购买数量需在 1–{MAX_GROUP_QUANTITY} 之间", 400)
    if course.course_type == "bundle" and quantity > 1:
        raise MallError("整包不支持批量购买", 400)

    learners = learners or []
    unit_price = money(course.price)
    original_amount = money(unit_price * quantity)
    discount = 0.0
    order_type = "normal"
    upgrade_sources: list[CoursePurchase] = []

    if course.course_type == "bundle" and quantity == 1:
        quote = upgrade_quote(db, user, course)
        if quote["eligible"]:
            if quote["payable"] <= 0:
                raise MallError("已拥有整包全部课程，无需再次购买", 409)
            discount = money(quote["discount"])
            order_type = "upgrade"
            upgrade_sources = quote["orders"]

    if renew:
        order_type = "renew"
    current = now()
    order = CoursePurchase(
        user_id=user.id,
        course_id=course.id,
        amount=money(max(original_amount - discount, 0)),
        channel=(channel or "mock").strip() or "mock",
        status="pending",
        created_at=current,
        order_no=unique_order_no(db, "C"),
        quantity=quantity,
        unit_price=unit_price,
        original_amount=original_amount,
        discount_amount=discount,
        order_type=order_type,
        upgrade_from_order_id=(
            upgrade_sources[0].id if len(upgrade_sources) == 1 else None
        ),
        expires_at=current + timedelta(minutes=ORDER_TTL_MINUTES),
        remark=(remark or "").strip(),
    )
    db.add(order)
    db.flush()

    _build_seats(db, order, user, quantity, learners)

    # 零元订单（抵扣后无需支付）直接完成，但仍留完整订单记录
    if order.amount <= 0:
        db.commit()
        db.refresh(order)
        pay_course_order(db, order, channel="mock", transaction_id="ZERO")
    else:
        db.commit()
        db.refresh(order)
    return order


def create_service_order(
    db: Session,
    user: User,
    product_id: int,
    channel: str = "mock",
    remark: str = "",
) -> ServicePurchase:
    product = db.get(ServiceProduct, product_id)
    if not product:
        raise MallError("服务不存在", 404)
    if user.role == "admin":
        raise MallError("管理员无需购买，已默认可查看全部服务", 400)
    if (product.status or "on") != "on":
        raise MallError("该服务已下架", 409)
    if has_service_access(db, user, product):
        raise MallError("已开通该服务，无需重复购买", 409)

    current = now()
    price = money(product.price)
    order = ServicePurchase(
        user_id=user.id,
        service_id=product.id,
        amount=price,
        channel=(channel or "mock").strip() or "mock",
        status="pending",
        created_at=current,
        order_no=unique_order_no(db, "S"),
        quantity=1,
        unit_price=price,
        original_amount=price,
        discount_amount=0.0,
        order_type="normal",
        expires_at=current + timedelta(minutes=ORDER_TTL_MINUTES),
        remark=(remark or "").strip(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    if order.amount <= 0:
        pay_service_order(db, order, channel="mock", transaction_id="ZERO")
    return order


# ---------- 支付 ----------


def _ensure_payable(order) -> None:
    current = now()
    if order.status == "pending" and order.expires_at and order.expires_at < current:
        order.status = "expired"
        raise MallError("订单已超时关闭，请重新下单", 409)


def pay_course_order(
    db: Session,
    order: CoursePurchase,
    channel: str = "mock",
    transaction_id: str = "",
) -> CoursePurchase:
    if order.status == "paid":
        return order  # 幂等：重复支付回调不重复开通
    if order.status == "refund_pending":
        raise MallError("订单退款处理中，无法支付", 409)
    if order.status != "pending":
        raise MallError(f"订单状态为 {order.status}，无法支付", 409)
    _ensure_payable(order)
    if order.status == "expired":
        db.commit()
        raise MallError("订单已超时关闭，请重新下单", 409)

    current = now()
    course = order_course(db, order)
    if not course:
        raise MallError("课程不存在", 404)

    order.status = "paid"
    order.channel = (channel or order.channel or "mock").strip() or "mock"
    order.transaction_id = (transaction_id or "").strip()
    order.paid_at = current
    valid_days = int(course.valid_days or 0)
    # 续期订单：新的到期时间从「当前剩余有效期」往后叠加，而不是从今天重算
    renew_base = current
    if order.order_type == "renew":
        existing = active_enrollment(db, order.user_id, order.course_id)
        if existing and existing.expires_at:
            renew_base = existing.expires_at
    order.valid_until = (
        renew_base + timedelta(days=valid_days) if valid_days > 0 else None
    )

    for seat in order.seats:
        if seat.status == "pending" and seat.learner_user_id:
            grant_course_enrollment(
                db,
                seat.learner_user_id,
                order.course_id,
                order,
                source="purchase" if order.quantity == 1 else "group",
                expires_at=order.valid_until,
            )
            seat.status = "activated"
            seat.activated_at = current

    # 升级订单支付后，标记被抵扣的旧订单，避免再次抵扣
    if order.order_type == "upgrade":
        included_ids = bundle_course_ids(db, course.id)
        sources = (
            db.query(CoursePurchase)
            .filter(
                CoursePurchase.user_id == order.user_id,
                CoursePurchase.status == "paid",
                CoursePurchase.course_id.in_(included_ids),
                CoursePurchase.upgraded_to_order_id.is_(None),
                CoursePurchase.id != order.id,
            )
            .all()
        )
        for source in sources:
            source.upgraded_to_order_id = order.id

    db.commit()
    db.refresh(order)
    return order


def pay_service_order(
    db: Session,
    order: ServicePurchase,
    channel: str = "mock",
    transaction_id: str = "",
) -> ServicePurchase:
    if order.status == "paid":
        return order
    if order.status != "pending":
        raise MallError(f"订单状态为 {order.status}，无法支付", 409)
    _ensure_payable(order)
    if order.status == "expired":
        db.commit()
        raise MallError("订单已超时关闭，请重新下单", 409)

    current = now()
    product = db.get(ServiceProduct, order.service_id)
    if not product:
        raise MallError("服务不存在", 404)

    order.status = "paid"
    order.channel = (channel or order.channel or "mock").strip() or "mock"
    order.transaction_id = (transaction_id or "").strip()
    order.paid_at = current
    order.valid_until = (
        current + timedelta(days=int(product.valid_days or 0))
        if int(product.valid_days or 0) > 0
        else None
    )
    grant_service_entitlement(
        db,
        order.user_id,
        order.service_id,
        order,
        source="purchase",
        expires_at=order.valid_until,
    )
    db.commit()
    db.refresh(order)
    return order


def cancel_course_order(db: Session, order: CoursePurchase) -> CoursePurchase:
    if order.status != "pending":
        raise MallError("只有待支付订单可以取消", 409)
    order.status = "cancelled"
    order.cancelled_at = now()
    db.commit()
    db.refresh(order)
    return order


def cancel_service_order(db: Session, order: ServicePurchase) -> ServicePurchase:
    if order.status != "pending":
        raise MallError("只有待支付订单可以取消", 409)
    order.status = "cancelled"
    order.cancelled_at = now()
    db.commit()
    db.refresh(order)
    return order


def expire_pending_orders(db: Session, order_no: str | None = None) -> int:
    current = now()
    total = 0
    for model in (CoursePurchase, ServicePurchase):
        query = db.query(model).filter(
            model.status == "pending",
            model.expires_at.isnot(None),
            model.expires_at < current,
        )
        if order_no:
            query = query.filter(model.order_no == order_no)
        total += query.update(
            {"status": "expired"}, synchronize_session=False
        )
    if total:
        db.commit()
    return total


# ---------- 退款 ----------


def _seat_refund_per_amount(order: CoursePurchase) -> float:
    if order.quantity <= 1:
        return money(order.amount)
    return money(order.unit_price)


def seat_is_refundable(
    db: Session, order: CoursePurchase, seat: CourseOrderSeat, current: datetime | None = None
) -> tuple[bool, str]:
    current = current or now()
    if seat.status == "refunded":
        return False, "该名额已退款"
    if order.channel == "admin":
        return False, "管理员开通的订单不涉及退款"
    if seat.status == "pending":
        return True, "未激活名额可退"
    if seat.status != "activated":
        return False, "名额状态异常"

    base = order.paid_at or order.created_at
    if seat.activated_at:
        base = seat.activated_at
    if current > base + timedelta(days=REFUND_WINDOW_DAYS):
        return False, f"已超过 {REFUND_WINDOW_DAYS} 天退款窗口"
    learner_id = seat.learner_user_id or order.user_id
    progress = order_progress_percent(db, order, learner_id)
    if progress >= REFUND_PROGRESS_LIMIT:
        return False, f"付费课时进度已达 {progress:.0f}%，超过 20% 上限"
    return True, "符合 7 天内且进度低于 20%"


def _course_refundable_seats(
    db: Session, order: CoursePurchase, force: bool = False
) -> list[CourseOrderSeat]:
    if force:
        return [seat for seat in order.seats if seat.status != "refunded"]
    return [
        seat
        for seat in order.seats
        if seat_is_refundable(db, order, seat)[0]
    ]


def refund_check(db: Session, order: CoursePurchase | ServicePurchase) -> dict:
    current = now()
    result = {
        "eligible": False,
        "reason": "",
        "refund_amount": 0.0,
        "within_window": False,
        "window_ends_at": None,
        "progress_percent": 0.0,
        "policy": REFUND_POLICY,
    }

    if isinstance(order, CoursePurchase):
        course = order_course(db, order)
        if order.status not in ("paid", "partially_refunded"):
            result["reason"] = "当前订单状态不可退款"
            return result
        if order.channel == "admin":
            result["reason"] = "管理员开通的订单不涉及退款"
            return result
        if not course:
            result["reason"] = "课程不存在"
            return result
        if order.upgraded_to_order_id:
            result["reason"] = "该订单已用于补差价升级；如需退款请先退整包订单"
            return result

        if order.seats:
            refundable = _course_refundable_seats(db, order)
            amount = money(
                sum(_seat_refund_per_amount(order) for _ in refundable)
            )
            # 展示用：取已激活名额中的最高进度
            progresses = [
                order_progress_percent(db, order, seat.learner_user_id or order.user_id)
                for seat in order.seats
                if seat.status == "activated"
            ]
            result["progress_percent"] = max(progresses, default=0.0)
            activated = [s for s in order.seats if s.status == "activated"]
            if activated:
                base = max(
                    (s.activated_at or order.paid_at or order.created_at)
                    for s in activated
                )
                result["window_ends_at"] = base + timedelta(days=REFUND_WINDOW_DAYS)
                result["within_window"] = current <= result["window_ends_at"]
            pending = [s for s in order.seats if s.status == "pending"]
            if pending:
                result["within_window"] = True
            result["eligible"] = bool(refundable)
            result["refund_amount"] = amount
            if not refundable:
                reasons = {
                    seat_is_refundable(db, order, s)[1] for s in order.seats
                }
                result["reason"] = "；".join(sorted(reasons)) or "无可退名额"
            elif pending:
                result["reason"] = f"可退未激活名额 {len(pending)} 个"
            else:
                result["reason"] = "符合 7 天内且付费进度低于 20% 的退款条件"
            return result

        # 历史订单（本次升级前创建，没有名额记录）
        base = order.paid_at or order.created_at
        result["window_ends_at"] = base + timedelta(days=REFUND_WINDOW_DAYS)
        result["within_window"] = current <= result["window_ends_at"]
        result["progress_percent"] = order_progress_percent(db, order, order.user_id)
        result["eligible"] = (
            result["within_window"]
            and result["progress_percent"] < REFUND_PROGRESS_LIMIT
        )
        result["refund_amount"] = money(order.amount) if result["eligible"] else 0.0
        if not result["within_window"]:
            result["reason"] = f"已超过 {REFUND_WINDOW_DAYS} 天退款窗口"
        elif result["progress_percent"] >= REFUND_PROGRESS_LIMIT:
            result["reason"] = (
                f"付费课时进度已达 {result['progress_percent']:.0f}%，"
                "超过 20% 上限"
            )
        else:
            result["reason"] = "符合 7 天内且付费进度低于 20% 的退款条件"
        return result

    # 服务订单：暂无使用记录，按 7 天窗口处理
    if order.status not in ("paid", "partially_refunded"):
        result["reason"] = "当前订单状态不可退款"
        return result
    if order.channel == "admin":
        result["reason"] = "管理员开通的订单不涉及退款"
        return result
    base = order.paid_at or order.created_at
    result["window_ends_at"] = base + timedelta(days=REFUND_WINDOW_DAYS)
    result["within_window"] = current <= result["window_ends_at"]
    if result["within_window"]:
        result["eligible"] = True
        result["refund_amount"] = money(order.amount)
        result["reason"] = "服务订单在 7 天内，可全额退款"
    else:
        result["reason"] = f"服务订单已超过 {REFUND_WINDOW_DAYS} 天退款窗口"
    return result


def apply_refund(
    db: Session,
    order: CoursePurchase | ServicePurchase,
    reason: str = "",
    force: bool = False,
) -> dict:
    """执行退款（模拟支付下立即完成）。返回退款金额与订单状态。"""
    check = refund_check(db, order)
    if not force:
        if not check["eligible"]:
            raise MallError(check["reason"] or "当前订单不可退款", 409)
    elif order.status not in ("paid", "partially_refunded", "refund_pending"):
        raise MallError("当前订单状态不可退款", 409)

    current = now()
    refunded_amount = 0.0

    if isinstance(order, CoursePurchase):
        seats = _course_refundable_seats(db, order, force=force)
        if not seats and not order.seats:
            # 历史无名额订单：整单退
            refunded_amount = money(order.amount)
            revoke_order_entitlements(db, order)
            order.status = "refunded"
            order.refunded_at = current
        elif not seats:
            raise MallError("没有可退款的名额", 409)
        else:
            for seat in seats:
                per = _seat_refund_per_amount(order)
                seat.refund_amount = per
                seat.status = "refunded"
                seat.refunded_at = current
                refunded_amount += per
                if seat.learner_user_id:
                    db.query(Enrollment).filter(
                        Enrollment.student_id == seat.learner_user_id,
                        Enrollment.course_id == order.course_id,
                        Enrollment.order_id == order.id,
                    ).delete(synchronize_session=False)
            remaining = [
                seat for seat in order.seats if seat.status != "refunded"
            ]
            if remaining:
                order.status = "partially_refunded"
            else:
                order.status = "refunded"
                order.refunded_at = current

        if order.status == "refunded" and order.order_type == "upgrade":
            # 退款后恢复旧单，允许再次补差价
            db.query(CoursePurchase).filter(
                CoursePurchase.upgraded_to_order_id == order.id
            ).update(
                {"upgraded_to_order_id": None}, synchronize_session=False
            )
    else:
        refunded_amount = money(order.amount)
        db.query(ServiceEntitlement).filter(
            ServiceEntitlement.order_id == order.id
        ).delete(synchronize_session=False)
        order.status = "refunded"
        order.refunded_at = current

    order.refund_amount = money(float(order.refund_amount or 0) + refunded_amount)
    reason = (reason or "").strip()
    if reason:
        order.refund_reason = (
            f"{order.refund_reason}；{reason}" if order.refund_reason else reason
        )
    db.commit()
    db.refresh(order)
    return {
        "refund_amount": money(refunded_amount),
        "status": order.status,
        "order_no": order.order_no,
    }


def request_refund(
    db: Session, order: CoursePurchase | ServicePurchase, reason: str = ""
) -> dict:
    """用户申请退款：模拟支付模式默认立即退款。"""
    auto = os.getenv("MALL_AUTO_REFUND", "1").strip() != "0"
    if auto:
        return apply_refund(db, order, reason=reason, force=False)
    check = refund_check(db, order)
    if not check["eligible"]:
        raise MallError(check["reason"] or "当前订单不可退款", 409)
    order.status = "refund_pending"
    if reason:
        order.refund_reason = reason
    db.commit()
    return {
        "refund_amount": 0.0,
        "status": order.status,
        "order_no": order.order_no,
    }


# ---------- 团购名额兑换 ----------


def redeem_seat(db: Session, user: User, activation_code: str) -> CourseOrderSeat:
    code = (activation_code or "").strip().upper()
    seat = (
        db.query(CourseOrderSeat)
        .filter(CourseOrderSeat.activation_code == code)
        .first()
    )
    if not seat:
        raise MallError("激活码无效", 404)
    order = seat.order
    if order is None:
        raise MallError("激活码对应的订单不存在", 404)
    if order.status not in ("paid", "partially_refunded"):
        raise MallError("订单未支付或已关闭，名额不可用", 409)
    if seat.status == "refunded":
        raise MallError("该名额已退款", 409)
    if seat.status == "activated":
        if seat.learner_user_id == user.id:
            return seat
        raise MallError("该名额已被其他学习者激活", 409)
    if seat.learner_user_id and seat.learner_user_id != user.id:
        raise MallError("该名额已绑定其他学习者", 409)

    course = order_course(db, order)
    if not course:
        raise MallError("课程不存在", 404)
    if has_course_access(db, user, course):
        raise MallError("你已拥有该课程，无需兑换该名额", 409)

    current = now()
    seat.learner_user_id = user.id
    seat.learner_name = seat.learner_name or user.full_name
    seat.status = "activated"
    seat.activated_at = current
    expires_at = order.valid_until
    if expires_at is None and int(course.valid_days or 0) > 0:
        expires_at = current + timedelta(days=int(course.valid_days))
    grant_course_enrollment(
        db,
        user.id,
        order.course_id,
        order,
        source="seat",
        expires_at=expires_at,
    )
    db.commit()
    db.refresh(seat)
    return seat


# ---------- 输出（序列化） ----------


def course_product_out(
    db: Session, course: Course, user: User, with_included: bool = True
) -> MallProductOut:
    owned, expires_at, _ = course_access_info(db, user, course)
    included: list[MallIncludedCourseOut] = []
    if with_included and course.course_type == "bundle":
        rows = (
            db.query(Course)
            .join(CourseBundleItem, CourseBundleItem.course_id == Course.id)
            .filter(CourseBundleItem.bundle_id == course.id)
            .order_by(CourseBundleItem.sort_order, CourseBundleItem.id)
            .all()
        )
        included = [
            MallIncludedCourseOut(
                id=item.id,
                name=item.name,
                path_label=item.path_label or "",
                price=money(item.price),
            )
            for item in rows
        ]
    badge = "免费" if course_is_free(course) else COURSE_TYPE_LABEL.get(
        course.course_type or "single", "单课"
    )
    return MallProductOut(
        product_type="course",
        id=course.id,
        name=course.name,
        subtitle=course.tagline or course.semester or "",
        description=course.description or "",
        price=money(course.price),
        original_price=(
            money(course.original_price)
            if course.original_price is not None
            else None
        ),
        cover_url=(course.cover_url or "").strip(),
        category=course.semester or "",
        unit_label=valid_days_label(int(course.valid_days or 0)),
        badge=badge,
        course_type=course.course_type or "single",
        path_label=course.path_label or "",
        valid_days=int(course.valid_days or 0),
        lesson_count=len(course_lessons(db, course)),
        trial_lesson_count=int(course.trial_lesson_count or 0),
        owned=owned,
        expires_at=expires_at,
        sort_order=int(course.sort_order or 0),
        included_courses=included,
    )


def service_product_out(
    db: Session, service: ServiceProduct, user: User
) -> MallProductOut:
    owned, expires_at, _ = service_access_info(db, user, service)
    return MallProductOut(
        product_type="service",
        id=service.id,
        name=service.name,
        subtitle=service.tagline or service.category or "",
        description=service.description or "",
        price=money(service.price),
        original_price=(
            money(service.original_price)
            if service.original_price is not None
            else None
        ),
        cover_url=(service.cover_url or "").strip(),
        category=service.category or "",
        unit_label=service.unit_label or "单次",
        badge=service.category or "服务",
        valid_days=int(service.valid_days or 0),
        owned=owned,
        expires_at=expires_at,
        sort_order=int(service.sort_order or 0),
    )


def course_product_detail(
    db: Session, course: Course, user: User
) -> MallProductDetailOut:
    base = course_product_out(db, course, user)
    quote = upgrade_quote_out(db, user, course) if course.course_type == "bundle" else None
    return MallProductDetailOut(
        **base.model_dump(),
        lessons=lesson_outs(db, course, user),
        upgrade_quote=quote,
        refund_policy=REFUND_POLICY,
    )


def service_product_detail(
    db: Session, service: ServiceProduct, user: User
) -> MallProductDetailOut:
    base = service_product_out(db, service, user)
    return MallProductDetailOut(
        **base.model_dump(),
        lessons=[],
        upgrade_quote=None,
        refund_policy=(
            "服务订单在购买后 7 天内可申请退款；超过 7 天请联系平台客服处理。"
        ),
    )


def seat_out(seat: CourseOrderSeat) -> MallOrderSeatOut:
    return MallOrderSeatOut(
        id=seat.id,
        learner_user_id=seat.learner_user_id,
        learner_name=seat.learner_name or "",
        learner_phone=seat.learner_phone or "",
        activation_code=seat.activation_code or "",
        status=seat.status or "pending",
        activated_at=seat.activated_at,
        refund_amount=money(seat.refund_amount),
        refunded_at=seat.refunded_at,
    )


def course_order_out(
    db: Session, order: CoursePurchase, viewer: User | None = None
) -> MallOrderOut:
    course = order_course(db, order)
    check = refund_check(db, order) if order.status in ("paid", "partially_refunded") else None
    source_nos = [
        row.order_no
        for row in db.query(CoursePurchase)
        .filter(CoursePurchase.upgraded_to_order_id == order.id)
        .all()
    ]
    current = now()
    can_pay = order.status == "pending" and (
        order.expires_at is None or order.expires_at >= current
    )
    return MallOrderOut(
        id=order.id,
        order_no=order.order_no or "",
        product_type="course",
        product_id=order.course_id,
        product_name=course.name if course else "",
        product_cover=(course.cover_url if course else "") or "",
        product_category=(course.semester if course else "") or "",
        quantity=int(order.quantity or 1),
        unit_price=money(order.unit_price),
        original_amount=money(order.original_amount),
        discount_amount=money(order.discount_amount),
        amount=money(order.amount),
        status=order.status or "pending",
        channel=order.channel or "mock",
        order_type=order.order_type or "normal",
        transaction_id=order.transaction_id or "",
        buyer_id=order.user_id,
        buyer_name=order.user.full_name if order.user else "",
        created_at=order.created_at,
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        valid_until=order.valid_until,
        cancelled_at=order.cancelled_at,
        refunded_at=order.refunded_at,
        refund_amount=money(order.refund_amount),
        refund_reason=order.refund_reason or "",
        upgrade_from_order_id=order.upgrade_from_order_id,
        upgrade_source_order_nos=source_nos,
        seats=[seat_out(seat) for seat in order.seats],
        can_pay=can_pay,
        can_cancel=order.status == "pending",
        refundable=bool(check and check["eligible"]),
        refund_hint=(check["reason"] if check else ""),
    )


def service_order_out(
    db: Session, order: ServicePurchase, viewer: User | None = None
) -> MallOrderOut:
    product = db.get(ServiceProduct, order.service_id)
    check = refund_check(db, order) if order.status in ("paid", "partially_refunded") else None
    current = now()
    can_pay = order.status == "pending" and (
        order.expires_at is None or order.expires_at >= current
    )
    return MallOrderOut(
        id=order.id,
        order_no=order.order_no or "",
        product_type="service",
        product_id=order.service_id,
        product_name=product.name if product else "",
        product_cover=(product.cover_url if product else "") or "",
        product_category=(product.category if product else "") or "",
        quantity=int(order.quantity or 1),
        unit_price=money(order.unit_price),
        original_amount=money(order.original_amount),
        discount_amount=money(order.discount_amount),
        amount=money(order.amount),
        status=order.status or "pending",
        channel=order.channel or "mock",
        order_type=order.order_type or "normal",
        transaction_id=order.transaction_id or "",
        buyer_id=order.user_id,
        buyer_name=order.user.full_name if order.user else "",
        created_at=order.created_at,
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        valid_until=order.valid_until,
        cancelled_at=order.cancelled_at,
        refunded_at=order.refunded_at,
        refund_amount=money(order.refund_amount),
        refund_reason=order.refund_reason or "",
        seats=[],
        can_pay=can_pay,
        can_cancel=order.status == "pending",
        refundable=bool(check and check["eligible"]),
        refund_hint=(check["reason"] if check else ""),
    )
