"""站内通知：提醒触发后的收件箱。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Notification, User
from ..notification_service import now
from ..schemas import NotificationListOut, NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def to_out(item: Notification) -> NotificationOut:
    return NotificationOut(
        id=item.id,
        user_id=item.user_id,
        reminder_id=item.reminder_id,
        course_id=item.course_id,
        course_name=item.course.name if item.course else "",
        trigger_key=item.trigger_key or "due",
        title=item.title,
        body=item.body or "",
        external_url=item.external_url or "",
        due_at=item.due_at,
        created_at=item.created_at,
        read_at=item.read_at,
        read=item.read_at is not None,
    )


@router.get("", response_model=NotificationListOut)
def list_notifications(
    unread_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    total = query.count()
    unread = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .count()
    )
    items = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return NotificationListOut(
        items=[to_out(item) for item in items],
        total=total,
        unread=unread,
        page=page,
        page_size=page_size,
    )


@router.get("/summary")
def notification_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    unread = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .count()
    )
    latest = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .first()
    )
    return {
        "unread": unread,
        "latest": to_out(latest) if latest else None,
    }


@router.post("/read-all")
def read_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current = now()
    updated = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .update({"read_at": current}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "updated": int(updated)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def read_one(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(Notification, notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="通知不存在")
    if item.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该通知")
    if item.read_at is None:
        item.read_at = now()
        db.commit()
        db.refresh(item)
    return to_out(item)
