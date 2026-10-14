from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Course, CourseMaterial, Enrollment, User
from ..schemas import MaterialCreate, MaterialOut

router = APIRouter(prefix="/api/materials", tags=["materials"])


def can_manage_course(user: User, course: Course) -> bool:
    if user.role == "admin":
        return True
    return user.role == "teacher" and course.teacher_id == user.id


def can_view_course(db: Session, user: User, course: Course) -> bool:
    if can_manage_course(user, course):
        return True
    if user.role == "student":
        return (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == user.id,
                Enrollment.course_id == course.id,
            )
            .first()
            is not None
        )
    return False


def to_out(m: CourseMaterial, user: User) -> MaterialOut:
    return MaterialOut(
        id=m.id,
        course_id=m.course_id,
        course_name=m.course.name if m.course else "",
        title=m.title,
        url=m.url or "",
        note=m.note or "",
        creator_id=m.creator_id,
        created_at=m.created_at,
        can_delete=can_manage_course(user, m.course) if m.course else user.role == "admin",
    )


@router.get("", response_model=list[MaterialOut])
def list_materials(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(CourseMaterial)
    if course_id is not None:
        course = db.get(Course, course_id)
        if not course or not can_view_course(db, user, course):
            raise HTTPException(status_code=403, detail="无权查看该课程资料")
        q = q.filter(CourseMaterial.course_id == course_id)
    else:
        if user.role == "student":
            ids = [
                e.course_id
                for e in db.query(Enrollment).filter(Enrollment.student_id == user.id).all()
            ]
            q = q.filter(CourseMaterial.course_id.in_(ids)) if ids else q.filter(False)
        elif user.role == "teacher":
            ids = [c.id for c in db.query(Course).filter(Course.teacher_id == user.id).all()]
            q = q.filter(CourseMaterial.course_id.in_(ids)) if ids else q.filter(False)
        # admin: all
    items = q.order_by(CourseMaterial.created_at.desc()).limit(200).all()
    return [to_out(m, user) for m in items]


@router.post("", response_model=MaterialOut)
def create_material(
    body: MaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if not can_manage_course(user, course):
        raise HTTPException(status_code=403, detail="仅课程教师或管理员可发布资料")
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="请填写标题")
    m = CourseMaterial(
        course_id=course.id,
        title=title,
        url=(body.url or "").strip(),
        note=(body.note or "").strip(),
        creator_id=user.id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return to_out(m, user)


@router.delete("/{material_id}")
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.get(CourseMaterial, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="资料不存在")
    if not m.course or not can_manage_course(user, m.course):
        raise HTTPException(status_code=403, detail="无权删除")
    db.delete(m)
    db.commit()
    return {"ok": True}
