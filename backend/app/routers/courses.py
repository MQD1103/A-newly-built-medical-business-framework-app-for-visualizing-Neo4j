from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Course, CoursePurchase, Enrollment, User
from ..schemas import CourseCreate, CourseOut, CoursePurchaseOut, EnrollmentCreate

router = APIRouter(prefix="/api/courses", tags=["courses"])


def enrolled_ids(db: Session, user: User) -> set[int]:
    if user.role == "admin":
        return {c.id for c in db.query(Course.id).all()}
    if user.role == "teacher":
        return {
            c.id
            for c in db.query(Course).filter(Course.teacher_id == user.id).all()
        }
    return {
        e.course_id
        for e in db.query(Enrollment).filter(Enrollment.student_id == user.id).all()
    }


def to_out(c: Course, owned: set[int] | None = None) -> CourseOut:
    return CourseOut(
        id=c.id,
        name=c.name,
        semester=c.semester,
        teacher_id=c.teacher_id,
        teacher_name=c.teacher.full_name if c.teacher else "",
        description=c.description or "",
        price=float(c.price if c.price is not None else 2.99),
        cover_url=(c.cover_url or "").strip(),
        enrolled=True if owned is None else c.id in owned,
    )


@router.get("", response_model=list[CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """售课目录：所有登录用户可见全部课程；enrolled 表示是否已关联/购买。"""
    owned = enrolled_ids(db, user)
    items = db.query(Course).order_by(Course.id).all()
    return [to_out(c, owned) for c in items]


@router.get("/all", response_model=list[CourseOut])
def list_all_courses(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    owned = enrolled_ids(db, user)
    return [to_out(c, owned) for c in db.query(Course).order_by(Course.id).all()]


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
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return to_out(course, enrolled_ids(db, user))


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
    db.add(Enrollment(student_id=body.student_id, course_id=body.course_id))
    db.commit()
    return {"ok": True}


@router.post("/{course_id}/purchase", response_model=CoursePurchaseOut)
def purchase_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """用户购买开通课程（模拟支付成功 → 写入订单 + 选课关联）。"""
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员无需购买，已默认可查看全部课程")

    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    owned = enrolled_ids(db, user)
    if course_id in owned:
        raise HTTPException(status_code=400, detail="已开通该课程，无需重复购买")

    amount = float(course.price if course.price is not None else 2.99)
    purchase = CoursePurchase(
        user_id=user.id,
        course_id=course.id,
        amount=amount,
        channel="mock",
        status="paid",
    )
    db.add(purchase)

    # 用户账号角色在库内仍为 student，沿用 Enrollment
    if user.role in ("student", "teacher"):
        exists = (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == user.id,
                Enrollment.course_id == course.id,
            )
            .first()
        )
        if not exists:
            db.add(Enrollment(student_id=user.id, course_id=course.id))

    db.commit()
    db.refresh(purchase)
    owned = enrolled_ids(db, user)
    return CoursePurchaseOut(
        id=purchase.id,
        course_id=course.id,
        course_name=course.name,
        amount=amount,
        channel=purchase.channel,
        status=purchase.status,
        created_at=purchase.created_at,
        course=to_out(course, owned),
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
        .limit(100)
        .all()
    )
    owned = enrolled_ids(db, user)
    return [
        CoursePurchaseOut(
            id=p.id,
            course_id=p.course_id,
            course_name=p.course.name if p.course else "",
            amount=float(p.amount),
            channel=p.channel,
            status=p.status,
            created_at=p.created_at,
            course=to_out(p.course, owned) if p.course else None,
        )
        for p in rows
    ]
