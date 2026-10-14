from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Course, Enrollment, Grade, User
from ..schemas import GradeCreate, GradeOut

router = APIRouter(prefix="/api/grades", tags=["grades"])


def can_manage_course(user: User, course: Course) -> bool:
    if user.role == "admin":
        return True
    return user.role == "teacher" and course.teacher_id == user.id


def to_out(g: Grade, user: User) -> GradeOut:
    return GradeOut(
        id=g.id,
        course_id=g.course_id,
        course_name=g.course.name if g.course else "",
        student_id=g.student_id,
        student_name=g.student.full_name if g.student else "",
        title=g.title,
        score=g.score,
        remark=g.remark or "",
        creator_id=g.creator_id,
        created_at=g.created_at,
        can_delete=can_manage_course(user, g.course) if g.course else user.role == "admin",
    )


@router.get("", response_model=list[GradeOut])
def list_grades(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Grade)
    if user.role == "student":
        q = q.filter(Grade.student_id == user.id)
        if course_id is not None:
            q = q.filter(Grade.course_id == course_id)
    elif user.role == "teacher":
        ids = [c.id for c in db.query(Course).filter(Course.teacher_id == user.id).all()]
        if course_id is not None:
            if course_id not in ids:
                raise HTTPException(status_code=403, detail="无权查看该课程成绩")
            q = q.filter(Grade.course_id == course_id)
        else:
            q = q.filter(Grade.course_id.in_(ids)) if ids else q.filter(False)
    else:
        # admin
        if course_id is not None:
            q = q.filter(Grade.course_id == course_id)
    items = q.order_by(Grade.created_at.desc()).limit(300).all()
    return [to_out(g, user) for g in items]


@router.get("/students")
def list_course_students(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """教师/管理员录入成绩时选择学生。"""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if not can_manage_course(user, course):
        raise HTTPException(status_code=403, detail="无权查看")
    rows = (
        db.query(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.course_id == course_id)
        .order_by(User.full_name)
        .all()
    )
    return [
        {"id": u.id, "full_name": u.full_name, "username": u.username}
        for _, u in rows
    ]


@router.post("", response_model=GradeOut)
def create_grade(
    body: GradeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if not can_manage_course(user, course):
        raise HTTPException(status_code=403, detail="仅课程教师或管理员可录入成绩")
    student = db.get(User, body.student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=400, detail="学生无效")
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == body.student_id,
            Enrollment.course_id == body.course_id,
        )
        .first()
    )
    if not enrolled:
        raise HTTPException(status_code=400, detail="该学生未选修此课")
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="请填写考核项")
    g = Grade(
        course_id=course.id,
        student_id=student.id,
        title=title,
        score=float(body.score),
        remark=(body.remark or "").strip(),
        creator_id=user.id,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return to_out(g, user)


@router.delete("/{grade_id}")
def delete_grade(
    grade_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    g = db.get(Grade, grade_id)
    if not g:
        raise HTTPException(status_code=404, detail="成绩不存在")
    if not g.course or not can_manage_course(user, g.course):
        raise HTTPException(status_code=403, detail="无权删除")
    db.delete(g)
    db.commit()
    return {"ok": True}
