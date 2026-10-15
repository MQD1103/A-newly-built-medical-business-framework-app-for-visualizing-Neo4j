from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import CalendarEvent, Course, Enrollment, ScheduleSlot, User
from ..schemas import (
    CalendarEventCreate,
    CalendarEventOut,
    ScheduleSlotCreate,
    ScheduleSlotOut,
)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def slot_out(s: ScheduleSlot) -> ScheduleSlotOut:
    return ScheduleSlotOut(
        id=s.id,
        course_id=s.course_id,
        course_name=s.course.name if s.course else "",
        weekday=s.weekday,
        start_time=s.start_time,
        end_time=s.end_time,
        location=s.location or "",
    )


@router.get("/slots", response_model=list[ScheduleSlotOut])
def list_slots(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ScheduleSlot)
    if user.role == "student":
        course_ids = [
            e.course_id
            for e in db.query(Enrollment).filter(Enrollment.student_id == user.id).all()
        ]
        q = q.filter(ScheduleSlot.course_id.in_(course_ids)) if course_ids else q.filter(False)
    elif user.role == "teacher":
        course_ids = [
            c.id for c in db.query(Course).filter(Course.teacher_id == user.id).all()
        ]
        q = q.filter(ScheduleSlot.course_id.in_(course_ids)) if course_ids else q.filter(False)
    slots = q.order_by(ScheduleSlot.weekday, ScheduleSlot.start_time).all()
    return [slot_out(s) for s in slots]


@router.post("/slots", response_model=ScheduleSlotOut)
def create_slot(
    body: ScheduleSlotCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该课程")
    slot = ScheduleSlot(
        course_id=body.course_id,
        weekday=body.weekday,
        start_time=body.start_time,
        end_time=body.end_time,
        location=body.location or "",
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot_out(slot)


@router.delete("/slots/{slot_id}")
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    slot = db.get(ScheduleSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="课表项不存在")
    if user.role == "teacher" and slot.course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该课程")
    db.delete(slot)
    db.commit()
    return {"ok": True}


@router.get("/events", response_model=list[CalendarEventOut])
def list_events(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return (
        db.query(CalendarEvent)
        .order_by(CalendarEvent.event_date.asc())
        .all()
    )


@router.post("/events", response_model=CalendarEventOut)
def create_event(
    body: CalendarEventCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    event = CalendarEvent(
        title=body.title,
        event_date=body.event_date,
        description=body.description or "",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    event = db.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="校历项不存在")
    db.delete(event)
    db.commit()
    return {"ok": True}


@router.get("/today", response_model=list[ScheduleSlotOut])
def today_slots(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Python: Monday=0 ... Sunday=6 — same as our model
    weekday = date.today().weekday()
    slots = list_slots(db=db, user=user)
    return [s for s in slots if s.weekday == weekday]
