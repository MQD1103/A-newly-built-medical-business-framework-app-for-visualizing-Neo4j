"""课程目录、课时、学习进度与购课。

售课主流程已迁到 mall_service（订单状态机/整包/升级/退款/团购），
这里保留前端正在使用的接口形状，并补充课时与进度接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import mall_service as mall
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    Course,
    CourseBundleItem,
    CoursePurchase,
    Enrollment,
    Lesson,
    LessonProgress,
    User,
)
from ..schemas import (
    BundleItemsIn,
    CourseCreate,
    CourseLessonsOut,
    CourseOut,
    CourseProgressOut,
    CoursePurchaseOut,
    CourseUpdate,
    EnrollmentCreate,
    LessonCreate,
    LessonOut,
    LessonProgressIn,
    LessonProgressOut,
    LessonUpdate,
)

router = APIRouter(prefix="/api/courses", tags=["courses"])


def enrolled_ids(db: Session, user: User) -> set[int]:
    return mall.accessible_course_ids(db, user)


def to_out(
    db: Session,
    c: Course,
    owned: set[int] | None = None,
    expires_at: object | None = None,
) -> CourseOut:
    owned_flag = True if owned is None else c.id in owned
    return CourseOut(
        id=c.id,
        name=c.name,
        semester=c.semester,
        teacher_id=c.teacher_id,
        teacher_name=c.teacher.full_name if c.teacher else "",
        description=c.description or "",
        price=float(c.price if c.price is not None else 2.99),
        cover_url=(c.cover_url or "").strip(),
        enrolled=owned_flag,
        course_type=c.course_type or "single",
        path_label=c.path_label or "",
        tagline=c.tagline or "",
        original_price=(
            float(c.original_price) if c.original_price is not None else None
        ),
        status=c.status or "on",
        sort_order=int(c.sort_order or 0),
        valid_days=int(c.valid_days or 0),
        trial_lesson_count=int(c.trial_lesson_count or 0),
        lesson_count=len(mall.course_lessons(db, c)),
        expires_at=expires_at,
    )


def with_access(
    db: Session, user: User, courses: list[Course]
) -> list[CourseOut]:
    owned = mall.accessible_course_ids(db, user)
    result: list[CourseOut] = []
    for c in courses:
        expiry = None
        if c.id in owned:
            _, expiry, _ = mall.course_access_info(db, user, c)
        result.append(to_out(db, c, owned, expiry))
    return result


@router.get("", response_model=list[CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """售课目录：非管理员只看在售课程；enrolled 表示当前是否有学习权。"""
    query = db.query(Course)
    if user.role != "admin":
        query = query.filter(Course.status == "on")
    items = query.order_by(Course.sort_order, Course.id).all()
    return with_access(db, user, items)


@router.get("/all", response_model=list[CourseOut])
def list_all_courses(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    items = db.query(Course).order_by(Course.sort_order, Course.id).all()
    return with_access(db, user, items)


@router.post("", response_model=CourseOut)
def create_course(
    body: CourseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    course = Course(
        name=body.name,
        semester=body.semester or "COPD 系列",
        teacher_id=body.teacher_id,
        description=body.description,
        price=float(body.price if body.price is not None else 2.99),
        cover_url=(body.cover_url or "").strip(),
        course_type=body.course_type or "single",
        path_label=(body.path_label or "").strip(),
        tagline=(body.tagline or "").strip(),
        original_price=body.original_price,
        status=body.status or "on",
        sort_order=int(body.sort_order or 0),
        valid_days=int(body.valid_days or 0),
        trial_lesson_count=int(body.trial_lesson_count or 0),
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return to_out(db, course, enrolled_ids(db, user))


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    body: CourseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    data = body.model_dump(exclude_unset=True)
    if "original_price" in data and data["original_price"] is None:
        course.original_price = None
        data.pop("original_price")
    for field, value in data.items():
        if field == "cover_url" and value is not None:
            value = value.strip()
        if field in ("path_label", "tagline") and value is not None:
            value = value.strip()
        setattr(course, field, value)
    db.commit()
    db.refresh(course)
    return to_out(db, course, enrolled_ids(db, user))


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if (course.status or "on") != "on" and user.role != "admin":
        if not mall.has_course_access(db, user, course):
            raise HTTPException(status_code=404, detail="课程不存在或已下架")
    return with_access(db, user, [course])[0]


# ---------- 整包内容（管理员维护） ----------


@router.get("/{course_id}/bundle-items", response_model=list[CourseOut])
def list_bundle_items(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bundle = db.get(Course, course_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="课程不存在")
    items = (
        db.query(Course)
        .join(CourseBundleItem, CourseBundleItem.course_id == Course.id)
        .filter(CourseBundleItem.bundle_id == course_id)
        .order_by(CourseBundleItem.sort_order, CourseBundleItem.id)
        .all()
    )
    return with_access(db, user, items)


@router.put("/{course_id}/bundle-items")
def set_bundle_items(
    course_id: int,
    body: BundleItemsIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    bundle = db.get(Course, course_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="课程不存在")
    if bundle.course_type != "bundle":
        raise HTTPException(status_code=400, detail="只有整包课程可以配置包含的单课")
    if course_id in body.course_ids:
        raise HTTPException(status_code=400, detail="整包不能包含自己")

    for item_id in body.course_ids:
        item = db.get(Course, item_id)
        if not item:
            raise HTTPException(status_code=400, detail=f"课程 {item_id} 不存在")
        if item.course_type == "bundle":
            raise HTTPException(status_code=400, detail="整包不能嵌套整包")

    db.query(CourseBundleItem).filter(
        CourseBundleItem.bundle_id == course_id
    ).delete()
    for index, item_id in enumerate(body.course_ids):
        db.add(
            CourseBundleItem(
                bundle_id=course_id,
                course_id=item_id,
                sort_order=index,
            )
        )
    db.commit()
    return {"ok": True, "count": len(body.course_ids)}


# ---------- 课时 ----------


@router.get("/{course_id}/lessons", response_model=CourseLessonsOut)
def list_lessons(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """课时列表：未购用户也能看到目录；只有试看节/已购课程返回视频地址。"""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    owned, _, _ = mall.course_access_info(db, user, course)
    progress = mall.course_progress(db, user.id, course)
    return CourseLessonsOut(
        course_id=course.id,
        course_name=course.name,
        owned=owned,
        is_free=mall.course_is_free(course),
        trial_lesson_count=int(course.trial_lesson_count or 0),
        total_lessons=progress["total_lessons"],
        completed_lessons=progress["completed_lessons"],
        progress_percent=progress["percent"],
        lessons=mall.lesson_outs(db, course, user),
    )


@router.post("/{course_id}/lessons", response_model=LessonOut)
def create_lesson(
    course_id: int,
    body: LessonCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    lesson = Lesson(
        course_id=course.id,
        title=body.title.strip(),
        summary=(body.summary or "").strip(),
        video_url=(body.video_url or "").strip(),
        duration_seconds=int(body.duration_seconds or 0),
        sort_order=int(body.sort_order or 0),
        is_trial=bool(body.is_trial),
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return LessonOut(
        id=lesson.id,
        course_id=lesson.course_id,
        title=lesson.title,
        summary=lesson.summary or "",
        video_url=lesson.video_url or "",
        duration_seconds=int(lesson.duration_seconds or 0),
        sort_order=int(lesson.sort_order or 0),
        is_trial=bool(lesson.is_trial),
        locked=False,
    )


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(
    lesson_id: int,
    body: LessonUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课时不存在")
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field in ("title", "summary", "video_url") and value is not None:
            value = value.strip()
        setattr(lesson, field, value)
    db.commit()
    db.refresh(lesson)
    return LessonOut(
        id=lesson.id,
        course_id=lesson.course_id,
        title=lesson.title,
        summary=lesson.summary or "",
        video_url=lesson.video_url or "",
        duration_seconds=int(lesson.duration_seconds or 0),
        sort_order=int(lesson.sort_order or 0),
        is_trial=bool(lesson.is_trial),
        locked=False,
    )


@router.delete("/lessons/{lesson_id}")
def delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课时不存在")
    db.query(LessonProgress).filter(
        LessonProgress.lesson_id == lesson_id
    ).delete(synchronize_session=False)
    db.delete(lesson)
    db.commit()
    return {"ok": True}


@router.post("/lessons/{lesson_id}/progress", response_model=LessonProgressOut)
def update_lesson_progress(
    lesson_id: int,
    body: LessonProgressIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上报续播位置/完播状态；退款规则按这里的付费课时完成数计算。"""
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课时不存在")
    course = db.get(Course, lesson.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    owned, _, _ = mall.course_access_info(db, user, course)
    if not mall.lesson_is_unlocked(course, lesson, owned):
        raise HTTPException(status_code=403, detail="该课时需购买后学习")

    duration = int(lesson.duration_seconds or 0)
    position = int(body.position_seconds or 0)
    if duration > 0:
        position = min(position, duration)

    row = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.user_id == user.id,
            LessonProgress.lesson_id == lesson.id,
        )
        .first()
    )
    current = mall.now()
    if not row:
        row = LessonProgress(
            user_id=user.id,
            course_id=course.id,
            lesson_id=lesson.id,
            position_seconds=0,
            completed=False,
            updated_at=current,
        )
        db.add(row)
    row.position_seconds = position
    if body.completed is not None:
        row.completed = bool(body.completed)
        row.completed_at = current if body.completed else None
    elif duration > 0 and position >= duration:
        row.completed = True
        row.completed_at = current
    row.updated_at = current
    db.commit()
    db.refresh(row)
    return LessonProgressOut(
        lesson_id=row.lesson_id,
        course_id=row.course_id,
        position_seconds=int(row.position_seconds or 0),
        completed=bool(row.completed),
        completed_at=row.completed_at,
        updated_at=row.updated_at,
    )


# ---------- 学习进度 ----------


@router.get("/{course_id}/progress", response_model=CourseProgressOut)
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    owned, _, _ = mall.course_access_info(db, user, course)
    lessons = mall.course_lessons(db, course)
    lesson_ids = [lesson.id for lesson in lessons]
    rows = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.user_id == user.id,
            LessonProgress.lesson_id.in_(lesson_ids),
        )
        .all()
        if lesson_ids
        else []
    )
    by_lesson = {row.lesson_id: row for row in rows}
    progress = mall.course_progress(db, user.id, course)
    items = []
    for lesson in lessons:
        row = by_lesson.get(lesson.id)
        items.append(
            LessonProgressOut(
                lesson_id=lesson.id,
                course_id=lesson.course_id,
                position_seconds=int(row.position_seconds or 0) if row else 0,
                completed=bool(row.completed) if row else False,
                completed_at=row.completed_at if row else None,
                updated_at=row.updated_at if row else None,
            )
        )
    return CourseProgressOut(
        course_id=course.id,
        owned=owned,
        total_lessons=progress["total_lessons"],
        completed_lessons=progress["completed_lessons"],
        percent=progress["percent"],
        paid_total=progress["paid_total"],
        paid_completed=progress["paid_completed"],
        paid_percent=progress["paid_percent"],
        lessons=items,
    )


# ---------- 兼容旧前端的购买接口 ----------


@router.post("/enrollments")
def enroll(
    body: EnrollmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    student = db.get(User, body.student_id)
    course = db.get(Course, body.course_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=400, detail="用户无效")
    if not course:
        raise HTTPException(status_code=400, detail="课程无效")
    exists = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == body.student_id,
            Enrollment.course_id == body.course_id,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="已关联该课")
    db.add(
        Enrollment(
            student_id=body.student_id,
            course_id=body.course_id,
            source="admin",
            granted_at=mall.now(),
            expires_at=None,
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/{course_id}/purchase", response_model=CoursePurchaseOut)
def purchase_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """兼容旧前端的「确认即支付」：内部走完整订单 → 模拟支付。"""
    try:
        order = mall.create_course_order(
            db, user, course_id, quantity=1, channel="mock"
        )
        if order.status == "pending":
            order = mall.pay_course_order(
                db, order, channel="mock", transaction_id="LEGACY"
            )
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    course = db.get(Course, order.course_id)
    owned = enrolled_ids(db, user)
    return CoursePurchaseOut(
        id=order.id,
        course_id=order.course_id,
        course_name=course.name if course else "",
        amount=float(order.amount or 0),
        channel=order.channel or "mock",
        status=order.status,
        created_at=order.created_at,
        course=to_out(
            db,
            course,
            owned,
            mall.course_access_info(db, user, course)[1] if course else None,
        )
        if course
        else None,
        order_no=order.order_no or "",
        quantity=int(order.quantity or 1),
        unit_price=float(order.unit_price or 0),
        original_amount=float(order.original_amount or 0),
        discount_amount=float(order.discount_amount or 0),
        order_type=order.order_type or "normal",
        transaction_id=order.transaction_id or "",
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        valid_until=order.valid_until,
        refund_amount=float(order.refund_amount or 0),
        refunded_at=order.refunded_at,
        refund_reason=order.refund_reason or "",
    )


@router.get("/purchases/mine", response_model=list[CoursePurchaseOut])
def my_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(CoursePurchase)
        .filter(CoursePurchase.user_id == user.id)
        .order_by(CoursePurchase.created_at.desc())
        .limit(200)
        .all()
    )
    owned = enrolled_ids(db, user)
    result: list[CoursePurchaseOut] = []
    for order in rows:
        course = db.get(Course, order.course_id)
        expiry = (
            mall.course_access_info(db, user, course)[1] if course else None
        )
        result.append(
            CoursePurchaseOut(
                id=order.id,
                course_id=order.course_id,
                course_name=course.name if course else "",
                amount=float(order.amount or 0),
                channel=order.channel or "mock",
                status=order.status or "paid",
                created_at=order.created_at,
                course=to_out(db, course, owned, expiry) if course else None,
                order_no=order.order_no or "",
                quantity=int(order.quantity or 1),
                unit_price=float(order.unit_price or 0),
                original_amount=float(order.original_amount or 0),
                discount_amount=float(order.discount_amount or 0),
                order_type=order.order_type or "normal",
                transaction_id=order.transaction_id or "",
                expires_at=order.expires_at,
                paid_at=order.paid_at,
                valid_until=order.valid_until,
                refund_amount=float(order.refund_amount or 0),
                refunded_at=order.refunded_at,
                refund_reason=order.refund_reason or "",
            )
        )
    return result
