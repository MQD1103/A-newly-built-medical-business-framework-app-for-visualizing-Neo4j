"""社区好友：加好友 / 申请同意 / 好友列表 / 私信。

关系只存一行（`FriendRequest`），用规范化用户对 low < high + 唯一约束，
方向由 `requester_id` 表达；两张新表都指向 users 多次，因此这里
一律不写 relationship()，对方用户都用 db.get / IN 查询解析。
"""

from dataclasses import dataclass, field
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import FriendMessage, FriendRequest, User
from ..schemas import (
    FriendMessageCreate,
    FriendMessageOut,
    FriendOut,
    FriendRequestCreate,
    FriendRequestOut,
    FriendRequestResultOut,
    FriendSummaryOut,
    FriendUserOut,
)

router = APIRouter(prefix="/api/friends", tags=["friends"])

MAX_SEARCH = 20
CHAT_PAGE = 200


@dataclass
class FriendView:
    """一次查询装下当前用户的全部关系，避免逐条再查。"""

    me: int
    friends: set[int] = field(default_factory=set)
    outgoing: set[int] = field(default_factory=set)  # 我发出、待验证
    incoming: set[int] = field(default_factory=set)  # 我收到、待处理
    pairs: dict[int, FriendRequest] = field(default_factory=dict)

    def state_of(self, other_id: int) -> str:
        if other_id == self.me:
            return "self"
        if other_id in self.friends:
            return "friends"
        if other_id in self.outgoing:
            return "pending_out"
        if other_id in self.incoming:
            return "pending_in"
        return "none"


def friend_view(db: Session, user_id: int) -> FriendView:
    view = FriendView(me=user_id)
    rows = (
        db.query(FriendRequest)
        .filter(
            or_(
                (FriendRequest.user_low_id == user_id),
                (FriendRequest.user_high_id == user_id),
            )
        )
        .all()
    )
    for r in rows:
        other = r.user_high_id if r.user_low_id == user_id else r.user_low_id
        view.pairs[other] = r
        if r.status == "accepted":
            view.friends.add(other)
        elif r.requester_id == user_id:
            view.outgoing.add(other)
        else:
            view.incoming.add(other)
    return view


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _find(db: Session, a: int, b: int) -> FriendRequest | None:
    low, high = _pair(a, b)
    return (
        db.query(FriendRequest)
        .filter(
            FriendRequest.user_low_id == low, FriendRequest.user_high_id == high
        )
        .first()
    )


def _user_out(u: User, state: str) -> FriendUserOut:
    return FriendUserOut(
        user_id=u.id,
        username=u.username,
        full_name=u.full_name,
        role=u.role,
        avatar_url=u.avatar_url or "",
        friend_state=state,
    )


def _users_by_id(db: Session, ids) -> dict[int, User]:
    if not ids:
        return {}
    rows = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: u for u in rows}


def _require_friend(db: Session, me: User, other_id: int) -> User:
    if other_id == me.id:
        raise HTTPException(status_code=400, detail="不能和自己私信")
    other = db.get(User, other_id)
    if not other:
        raise HTTPException(status_code=404, detail="用户不存在")
    row = _find(db, me.id, other.id)
    if not row or row.status != "accepted":
        raise HTTPException(status_code=403, detail="你们还不是好友")
    return other


# ---------- 字面量路径放在前面，避免被 /{user_id} 之类的动态段遮蔽 ----------


@router.get("", response_model=list[FriendOut])
def list_friends(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    view = friend_view(db, user.id)
    if not view.friends:
        return []

    unread = dict(
        db.query(FriendMessage.sender_id, func.count(FriendMessage.id))
        .filter(
            FriendMessage.recipient_id == user.id,
            FriendMessage.read_at.is_(None),
            FriendMessage.sender_id.in_(view.friends),
        )
        .group_by(FriendMessage.sender_id)
        .all()
    )

    # 每个好友的最后一条消息：一次倒序查询，首见即最新
    recent = (
        db.query(FriendMessage)
        .filter(
            or_(
                and_(
                    FriendMessage.sender_id == user.id,
                    FriendMessage.recipient_id.in_(view.friends),
                ),
                and_(
                    FriendMessage.recipient_id == user.id,
                    FriendMessage.sender_id.in_(view.friends),
                ),
            )
        )
        .order_by(FriendMessage.id.desc())
        .limit(2000)
        .all()
    )
    last: dict[int, FriendMessage] = {}
    for m in recent:
        other = m.recipient_id if m.sender_id == user.id else m.sender_id
        if other not in last:
            last[other] = m

    users = _users_by_id(db, view.friends)
    rows: list[tuple[datetime, FriendOut]] = []
    for fid, u in users.items():
        m = last.get(fid)
        pair = view.pairs.get(fid)
        if m:
            when = m.created_at
        elif pair:
            when = pair.accepted_at or pair.created_at
        else:
            when = datetime.min
        rows.append(
            (
                when,
                FriendOut(
                    **_user_out(u, "friends").model_dump(),
                    last_message=(m.content[:30] if m else ""),
                    last_message_at=(m.created_at if m else None),
                    unread_count=unread.get(fid, 0),
                ),
            )
        )
    rows.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in rows]


@router.get("/requests", response_model=list[FriendRequestOut])
def list_incoming_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    view = friend_view(db, user.id)
    return _request_out(db, view, view.incoming, "incoming")


@router.get("/requests/sent", response_model=list[FriendRequestOut])
def list_sent_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    view = friend_view(db, user.id)
    return _request_out(db, view, view.outgoing, "outgoing")


def _request_out(
    db: Session, view: FriendView, ids: set[int], direction: str
) -> list[FriendRequestOut]:
    if not ids:
        return []
    users = _users_by_id(db, ids)
    rows: list[tuple[datetime, FriendRequestOut]] = []
    for other_id in ids:
        pair = view.pairs.get(other_id)
        u = users.get(other_id)
        if not pair or not u:
            continue
        rows.append(
            (
                pair.created_at,
                FriendRequestOut(
                    **_user_out(u, view.state_of(other_id)).model_dump(),
                    request_id=pair.id,
                    created_at=pair.created_at,
                    direction=direction,
                ),
            )
        )
    rows.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in rows]


@router.get("/search", response_model=list[FriendUserOut])
def search_users(
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    term = (q or "").strip()
    if not term:
        return []
    like = f"%{term}%"
    rows = (
        db.query(User)
        .filter(User.id != user.id)
        .filter(or_(User.username.ilike(like), User.full_name.ilike(like)))
        .order_by(
            case(
                (User.username == term, 0),
                (User.full_name == term, 1),
                else_=2,
            ),
            User.id.asc(),
        )
        .limit(MAX_SEARCH)
        .all()
    )
    view = friend_view(db, user.id)
    return [_user_out(u, view.state_of(u.id)) for u in rows]


@router.get("/summary", response_model=FriendSummaryOut)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    view = friend_view(db, user.id)
    unread = 0
    if view.friends:
        # 只算「仍是好友」的发送者，否则删好友后未读红点永远消不掉
        unread = (
            db.query(func.count(FriendMessage.id))
            .filter(
                FriendMessage.recipient_id == user.id,
                FriendMessage.read_at.is_(None),
                FriendMessage.sender_id.in_(view.friends),
            )
            .scalar()
        ) or 0
    pending = len(view.incoming)
    return FriendSummaryOut(
        pending_requests=pending, unread_messages=unread, total=pending + unread
    )


@router.post("/requests", response_model=FriendRequestResultOut)
def request_friend(
    body: FriendRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.user_id == user.id:
        raise HTTPException(status_code=400, detail="不能添加自己为好友")
    target = db.get(User, body.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    row = _find(db, user.id, target.id)
    if row and row.status == "accepted":
        raise HTTPException(status_code=400, detail="你们已经是好友")
    if row and row.requester_id == user.id:
        raise HTTPException(status_code=400, detail="已发送过申请，等待对方验证")
    if row:
        # 对方已经申请过我，这次视为直接同意
        row.status = "accepted"
        row.accepted_at = datetime.utcnow()
        db.commit()
        return FriendRequestResultOut(
            request_id=row.id,
            user_id=target.id,
            status="accepted",
            auto_accepted=True,
        )

    low, high = _pair(user.id, target.id)
    row = FriendRequest(
        user_low_id=low,
        user_high_id=high,
        requester_id=user.id,
        status="pending",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # 并发下同一对用户被同时插入，重查后按已有关系处理
        db.rollback()
        row = _find(db, user.id, target.id)
        if row and row.status == "accepted":
            raise HTTPException(status_code=400, detail="你们已经是好友")
        raise HTTPException(status_code=400, detail="已发送过申请，等待对方验证")
    db.refresh(row)
    return FriendRequestResultOut(
        request_id=row.id, user_id=target.id, status="pending", auto_accepted=False
    )


@router.post("/requests/{request_id}/accept", response_model=FriendRequestResultOut)
def accept_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(FriendRequest, request_id)
    # 非当事方一律 404，不泄露申请是否存在
    if not row or user.id not in (row.user_low_id, row.user_high_id):
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.requester_id == user.id:
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.status == "accepted":
        raise HTTPException(status_code=400, detail="你们已经是好友")
    row.status = "accepted"
    row.accepted_at = datetime.utcnow()
    db.commit()
    other_id = row.user_high_id if row.user_low_id == user.id else row.user_low_id
    return FriendRequestResultOut(request_id=row.id, user_id=other_id, status="accepted")


@router.get("/{user_id}/messages", response_model=list[FriendMessageOut])
def list_messages(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_friend(db, user, user_id)
    rows = (
        db.query(FriendMessage)
        .filter(
            or_(
                and_(
                    FriendMessage.sender_id == user.id,
                    FriendMessage.recipient_id == user_id,
                ),
                and_(
                    FriendMessage.sender_id == user_id,
                    FriendMessage.recipient_id == user.id,
                ),
            )
        )
        .order_by(FriendMessage.id.desc())
        .limit(CHAT_PAGE)
        .all()
    )
    rows.reverse()
    # 打开会话即已读（项目没有推送通道，这是最省事且自洽的做法）
    db.query(FriendMessage).filter(
        FriendMessage.sender_id == user_id,
        FriendMessage.recipient_id == user.id,
        FriendMessage.read_at.is_(None),
    ).update({FriendMessage.read_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return [
        FriendMessageOut(
            id=m.id,
            sender_id=m.sender_id,
            recipient_id=m.recipient_id,
            content=m.content,
            created_at=m.created_at,
            mine=m.sender_id == user.id,
        )
        for m in rows
    ]


@router.post("/{user_id}/messages", response_model=FriendMessageOut)
def send_message(
    user_id: int,
    body: FriendMessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_friend(db, user, user_id)
    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="请填写内容")
    m = FriendMessage(sender_id=user.id, recipient_id=user_id, content=text)
    db.add(m)
    db.commit()
    db.refresh(m)
    return FriendMessageOut(
        id=m.id,
        sender_id=m.sender_id,
        recipient_id=m.recipient_id,
        content=m.content,
        created_at=m.created_at,
        mine=True,
    )


@router.delete("/{user_id}")
def remove_friend(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """统一删除入口：删好友 / 拒绝申请 / 撤销申请都走这里。

    只删关系行，聊天记录保留（重新加回仍能看到历史）。
    """
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    row = _find(db, user.id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="好友关系不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
