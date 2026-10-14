from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Notice, User
from ..schemas import NoticeCreate, NoticeOut

router = APIRouter(prefix="/api/notices", tags=["notices"])


def to_out(n: Notice) -> NoticeOut:
    return NoticeOut(
        id=n.id,
        title=n.title,
        body=n.body,
        audience=n.audience,
        is_urgent=bool(n.is_urgent),
        author_id=n.author_id,
        author_name=n.author.full_name if n.author else "",
        created_at=n.created_at,
    )


def visible_for(user: User, notice: Notice) -> bool:
    if notice.audience == "all":
        return True
    if user.role == "admin":
        return True
    return notice.audience == user.role


@router.get("", response_model=list[NoticeOut])
def list_notices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notices = db.query(Notice).order_by(Notice.created_at.desc()).all()
    return [to_out(n) for n in notices if visible_for(user, n)]


@router.get("/{notice_id}", response_model=NoticeOut)
def get_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notice = db.get(Notice, notice_id)
    if not notice or not visible_for(user, notice):
        raise HTTPException(status_code=404, detail="公告不存在")
    return to_out(notice)


@router.post("", response_model=NoticeOut)
def create_notice(
    body: NoticeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    notice = Notice(
        title=body.title,
        body=body.body,
        audience=body.audience,
        is_urgent=bool(body.is_urgent),
        author_id=user.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return to_out(notice)


@router.delete("/{notice_id}")
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="公告不存在")
    db.delete(notice)
    db.commit()
    return {"ok": True}
