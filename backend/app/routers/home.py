from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CalendarEvent, Notification, User
from ..schemas import HomeOut
from .notices import list_notices
from .reminders import list_reminders
from .schedule import list_slots

router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("", response_model=HomeOut)
def home_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    weekday = date.today().weekday()
    all_slots = list_slots(db=db, user=user)
    today_slots = [s for s in all_slots if s.weekday == weekday]

    reminders = [
        r
        for r in list_reminders(db=db, user=user)
        if r.notify_enabled and not r.completed
    ]
    # 临近：未过期前 7 天内 + 已过期最近 3 条
    upcoming = []
    overdue_recent = []
    horizon = datetime.utcnow() + timedelta(days=7)
    past_cutoff = datetime.utcnow() - timedelta(days=14)
    for r in reminders:
        if r.due_at >= datetime.utcnow() and r.due_at <= horizon:
            upcoming.append(r)
        elif r.due_at < datetime.utcnow() and r.due_at >= past_cutoff:
            overdue_recent.append(r)
    upcoming_reminders = (overdue_recent + upcoming)[:8]

    notices = list_notices(db=db, user=user)[:5]

    today = date.today()
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.event_date >= today)
        .order_by(CalendarEvent.event_date.asc())
        .limit(5)
        .all()
    )

    unread_notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .count()
    )

    return HomeOut(
        today_slots=today_slots,
        upcoming_reminders=upcoming_reminders,
        latest_notices=notices,
        upcoming_events=events,
        unread_notifications=unread_notifications,
    )
