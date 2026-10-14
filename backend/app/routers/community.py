import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CommunityComment, CommunityLike, CommunityPost, User
from ..schemas import (
    CommunityCommentCreate,
    CommunityCommentOut,
    CommunityImageOut,
    CommunityOriginalOut,
    CommunityPostCreate,
    CommunityPostOut,
    CommunityRepostCreate,
)

router = APIRouter(prefix="/api/community", tags=["community"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "community"
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_IMAGES = 9


def parse_images(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if x]
    except json.JSONDecodeError:
        pass
    return []


def like_count(db: Session, post_id: int) -> int:
    return db.query(CommunityLike).filter(CommunityLike.post_id == post_id).count()


def comment_count(db: Session, post_id: int) -> int:
    return db.query(CommunityComment).filter(CommunityComment.post_id == post_id).count()


def share_count(db: Session, post_id: int) -> int:
    return (
        db.query(CommunityPost)
        .filter(CommunityPost.original_post_id == post_id)
        .count()
    )


def liked_by(db: Session, post_id: int, user_id: int) -> bool:
    return (
        db.query(CommunityLike)
        .filter(CommunityLike.post_id == post_id, CommunityLike.user_id == user_id)
        .first()
        is not None
    )


def original_out(p: CommunityPost | None) -> CommunityOriginalOut | None:
    if not p:
        return None
    return CommunityOriginalOut(
        id=p.id,
        author_name=p.author.full_name if p.author else "",
        content=p.content or "",
        image_urls=parse_images(p.image_urls),
    )


def to_out(p: CommunityPost, user: User, db: Session) -> CommunityPostOut:
    orig = None
    if p.original_post_id:
        src = p.original or db.get(CommunityPost, p.original_post_id)
        orig = original_out(src)
    return CommunityPostOut(
        id=p.id,
        author_id=p.author_id,
        author_name=p.author.full_name if p.author else "",
        author_role=p.author.role if p.author else "",
        author_avatar_url=(p.author.avatar_url if p.author else "") or "",
        content=p.content or "",
        image_urls=parse_images(p.image_urls),
        created_at=p.created_at,
        can_delete=p.author_id == user.id or user.role == "admin",
        like_count=like_count(db, p.id),
        liked_by_me=liked_by(db, p.id, user.id),
        comment_count=comment_count(db, p.id),
        share_count=share_count(db, p.id),
        original_post_id=p.original_post_id,
        original=orig,
    )


def comment_to_out(c: CommunityComment, user: User) -> CommunityCommentOut:
    return CommunityCommentOut(
        id=c.id,
        post_id=c.post_id,
        author_id=c.author_id,
        author_name=c.author.full_name if c.author else "",
        author_avatar_url=(c.author.avatar_url if c.author else "") or "",
        content=c.content,
        created_at=c.created_at,
        can_delete=c.author_id == user.id or user.role == "admin",
    )


@router.get("/posts", response_model=list[CommunityPostOut])
def list_posts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(CommunityPost)
        .order_by(CommunityPost.created_at.desc())
        .limit(100)
        .all()
    )
    return [to_out(p, user, db) for p in items]


@router.post("/upload", response_model=CommunityImageOut)
async def upload_community_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = ALLOWED_TYPES[file.content_type]
    filename = f"{user.id}_{uuid4().hex[:10]}{ext}"
    dest = UPLOAD_DIR / filename
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="单张图片不能超过 5MB")
    dest.write_bytes(data)
    return CommunityImageOut(url=f"/uploads/community/{filename}")


@router.post("/posts", response_model=CommunityPostOut)
def create_post(
    body: CommunityPostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = (body.content or "").strip()
    images = [u.strip() for u in (body.image_urls or []) if u and u.strip()]
    if len(images) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"最多上传 {MAX_IMAGES} 张图片")
    if not content and not images:
        raise HTTPException(status_code=400, detail="请填写文字或添加照片")

    for url in images:
        if not url.startswith("/uploads/community/"):
            raise HTTPException(status_code=400, detail="图片地址无效")

    post = CommunityPost(
        author_id=user.id,
        content=content,
        image_urls=json.dumps(images, ensure_ascii=False),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return to_out(post, user, db)


@router.post("/posts/{post_id}/like", response_model=CommunityPostOut)
def toggle_like(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = db.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    existing = (
        db.query(CommunityLike)
        .filter(CommunityLike.post_id == post_id, CommunityLike.user_id == user.id)
        .first()
    )
    if existing:
        db.delete(existing)
    else:
        db.add(CommunityLike(post_id=post_id, user_id=user.id))
    db.commit()
    db.refresh(post)
    return to_out(post, user, db)


@router.post("/posts/{post_id}/repost", response_model=CommunityPostOut)
def repost(
    post_id: int,
    body: CommunityRepostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    src = db.get(CommunityPost, post_id)
    if not src:
        raise HTTPException(status_code=404, detail="动态不存在")
    # 转发链指向原始帖：若源已是转发，则挂到最源头
    root_id = src.original_post_id or src.id
    root = db.get(CommunityPost, root_id) or src
    post = CommunityPost(
        author_id=user.id,
        content=(body.content or "").strip(),
        image_urls="[]",
        original_post_id=root.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return to_out(post, user, db)


@router.get("/posts/{post_id}/comments", response_model=list[CommunityCommentOut])
def list_comments(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = db.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    rows = (
        db.query(CommunityComment)
        .filter(CommunityComment.post_id == post_id)
        .order_by(CommunityComment.created_at.asc())
        .limit(200)
        .all()
    )
    return [comment_to_out(c, user) for c in rows]


@router.post("/posts/{post_id}/comments", response_model=CommunityCommentOut)
def create_comment(
    post_id: int,
    body: CommunityCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = db.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="请填写评论内容")
    c = CommunityComment(post_id=post_id, author_id=user.id, content=text)
    db.add(c)
    db.commit()
    db.refresh(c)
    return comment_to_out(c, user)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.get(CommunityComment, comment_id)
    if not c:
        raise HTTPException(status_code=404, detail="评论不存在")
    if c.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只能删除自己的评论")
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = db.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    if post.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只能删除自己的动态")
    # 断开指向本帖的转发（保留转发文案，清空原帖引用）
    db.query(CommunityPost).filter(CommunityPost.original_post_id == post_id).update(
        {CommunityPost.original_post_id: None}
    )
    db.query(CommunityLike).filter(CommunityLike.post_id == post_id).delete()
    db.query(CommunityComment).filter(CommunityComment.post_id == post_id).delete()
    db.delete(post)
    db.commit()
    return {"ok": True}
