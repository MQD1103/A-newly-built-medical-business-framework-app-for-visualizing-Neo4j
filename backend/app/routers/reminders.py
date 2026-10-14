from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Course, Enrollment, Reminder, ReminderPreference, User
from ..schemas import ReminderCreate, ReminderNotifyUpdate, ReminderOut, ReminderUpdate

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def reminder_status(due_at: datetime) -> str:
    return "overdue" if due_at < datetime.utcnow() else "pending"


def get_notify_enabled(db: Session, user_id: int, reminder_id: int) -> bool:
    pref = (
        db.query(ReminderPreference)
        .filter(
            ReminderPreference.user_id == user_id,
            ReminderPreference.reminder_id == reminder_id,
        )
        .first()
    )
    return True if pref is None else bool(pref.enabled)


def can_edit_reminder(user: User, reminder: Reminder) -> bool:
    source = reminder.source or "manager"
    if source == "user":
        return reminder.creator_id == user.id
    if source == "system":
        return user.role == "admin"
    # manager
    if user.role == "admin":
        return True
    if user.role == "teacher" and reminder.course and reminder.course.teacher_id == user.id:
        return True
    return reminder.creator_id == user.id and user.role in ("admin", "teacher")


def to_out(r: Reminder, user: User, db: Session) -> ReminderOut:
    source = r.source or "manager"
    return ReminderOut(
        id=r.id,
        course_id=r.course_id,
        course_name=r.course.name if r.course else "",
        title=r.title,
        content=r.content or "",
        due_at=r.due_at,
        external_url=r.external_url or "",
        creator_id=r.creator_id,
        created_at=r.created_at,
        status=reminder_status(r.due_at),
        source=source,
        notify_enabled=get_notify_enabled(db, user.id, r.id),
        can_delete=source == "user" and r.creator_id == user.id,
        can_edit=can_edit_reminder(user, r),
    )


def can_manage_course(user: User, course: Course) -> bool:
    if user.role == "admin":
        return True
    if user.role == "teacher" and course.teacher_id == user.id:
        return True
    return False


def student_enrolled(db: Session, user: User, course_id: int) -> bool:
    return (
        db.query(Enrollment)
        .filter(Enrollment.student_id == user.id, Enrollment.course_id == course_id)
        .first()
        is not None
    )


def user_can_see(db: Session, user: User, reminder: Reminder) -> bool:
    if reminder.creator_id == user.id:
        return True
    if user.role == "admin":
        return True
    if user.role == "teacher":
        return bool(reminder.course and reminder.course.teacher_id == user.id)
    if user.role == "student" and reminder.course_id:
        return student_enrolled(db, user, reminder.course_id)
    return False


@router.get("", response_model=list[ReminderOut])
def list_reminders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Reminder)
    own = (Reminder.creator_id == user.id)
    if user.role == "admin":
        pass
    elif user.role == "student":
        course_ids = [
            e.course_id
            for e in db.query(Enrollment).filter(Enrollment.student_id == user.id).all()
        ]
        if course_ids:
            q = q.filter(or_(own, Reminder.course_id.in_(course_ids)))
        else:
            q = q.filter(own)
    elif user.role == "teacher":
        course_ids = [
            c.id for c in db.query(Course).filter(Course.teacher_id == user.id).all()
        ]
        if course_ids:
            q = q.filter(or_(own, Reminder.course_id.in_(course_ids)))
        else:
            q = q.filter(own)
    items = q.order_by(Reminder.due_at.asc()).all()
    return [to_out(r, user, db) for r in items]


@router.post("", response_model=ReminderOut)
def create_reminder(
    body: ReminderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任意事项均可添加；课程可选，无课程强制限制。"""
    course = None
    course_id = body.course_id
    if course_id is not None:
        course = db.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="课程不存在")

    # 关联课程且为该课管理者 → 管理发布；否则个人事项（可删）
    if (
        course is not None
        and user.role in ("admin", "teacher")
        and can_manage_course(user, course)
    ):
        source = "manager"
    else:
        source = "user"

    reminder = Reminder(
        course_id=course_id,
        title=body.title.strip(),
        content=(body.content or "").strip(),
        due_at=body.due_at,
        external_url=(body.external_url or "").strip(),
        creator_id=user.id,
        source=source,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return to_out(reminder, user, db)


@router.patch("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int,
    body: ReminderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if not can_edit_reminder(user, reminder):
        raise HTTPException(status_code=403, detail="无权编辑该提醒")
    if body.title is not None:
        reminder.title = body.title.strip()
    if body.content is not None:
        reminder.content = body.content.strip()
    if body.due_at is not None:
        reminder.due_at = body.due_at
    if body.external_url is not None:
        reminder.external_url = body.external_url.strip()
    db.commit()
    db.refresh(reminder)
    return to_out(reminder, user, db)


@router.put("/{reminder_id}/notify", response_model=ReminderOut)
def set_reminder_notify(
    reminder_id: int,
    body: ReminderNotifyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """管理者/系统提醒：用户可开关「是否提醒」，但不能删除。"""
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if not user_can_see(db, user, reminder):
        raise HTTPException(status_code=403, detail="无权操作")
    source = reminder.source or "manager"
    if source not in ("manager", "system"):
        raise HTTPException(status_code=400, detail="个人提醒无需此开关")

    pref = (
        db.query(ReminderPreference)
        .filter(
            ReminderPreference.user_id == user.id,
            ReminderPreference.reminder_id == reminder_id,
        )
        .first()
    )
    if pref is None:
        pref = ReminderPreference(
            user_id=user.id,
            reminder_id=reminder_id,
            enabled=body.enabled,
        )
        db.add(pref)
    else:
        pref.enabled = body.enabled
    db.commit()
    db.refresh(reminder)
    return to_out(reminder, user, db)


@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    source = reminder.source or "manager"
    if source in ("manager", "system"):
        raise HTTPException(status_code=403, detail="管理者或系统添加的提醒不可删除")
    if reminder.creator_id != user.id:
        raise HTTPException(status_code=403, detail="只能删除自己添加的提醒")
    db.query(ReminderPreference).filter(ReminderPreference.reminder_id == reminder_id).delete()
    db.delete(reminder)
    db.commit()
    return {"ok": True}
