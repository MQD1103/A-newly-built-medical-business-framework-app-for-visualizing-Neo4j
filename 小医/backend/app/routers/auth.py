from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import User
from ..schemas import (
    AvatarPreviewOut,
    ImpersonateIn,
    ImpersonateOut,
    LoginRequest,
    ProfileUpdate,
    Token,
    UserOut,
)

# 「以此用户身份进入」的令牌有效期（比正常登录短）
IMPERSONATE_MINUTES = 120

router = APIRouter(prefix="/api/auth", tags=["auth"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "avatars"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(access_token=token)


@router.post("/impersonate", response_model=ImpersonateOut)
def impersonate(
    body: ImpersonateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """管理员换用目标用户的身份令牌，用于「以此用户身份进入」。

    现有 get_current_user 只读 JWT 的 sub，所以这个令牌在所有端点下与目标用户
    自己登录完全等价（creator_id / user_id 都记成目标用户）；act 只是审计预留。
    """
    if body.user_id == admin.id:
        raise HTTPException(status_code=400, detail="当前已是本人身份")
    target = db.get(User, body.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="不能切换为其他管理员身份")

    token = create_access_token(
        {"sub": str(target.id), "role": target.role, "act": str(admin.id)},
        expires_delta=timedelta(minutes=IMPERSONATE_MINUTES),
    )
    return ImpersonateOut(access_token=token, user=UserOut.model_validate(target))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """修改姓名；若改密码需提供旧密码。"""
    if body.full_name is not None:
        name = body.full_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="姓名不能为空")
        user.full_name = name

    if body.new_password:
        if not body.old_password:
            raise HTTPException(status_code=400, detail="请填写当前密码")
        if not verify_password(body.old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        user.password_hash = hash_password(body.new_password)

    if body.full_name is None and not body.new_password:
        raise HTTPException(status_code=400, detail="没有需要更新的内容")

    db.commit()
    db.refresh(user)
    return user


@router.get("/avatar-preview", response_model=AvatarPreviewOut)
def avatar_preview(username: str, db: Session = Depends(get_db)):
    """登录页预览：未设置头像返回 null，前端继续显示蓝球。"""
    name = username.strip()
    if not name:
        return AvatarPreviewOut(username="", avatar_url=None)
    user = db.query(User).filter(User.username == name).first()
    if not user or not user.avatar_url:
        return AvatarPreviewOut(username=name, avatar_url=None)
    return AvatarPreviewOut(username=name, avatar_url=user.avatar_url)


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }[file.content_type]
    filename = f"{user.username}_{uuid4().hex[:8]}{ext}"
    dest = UPLOAD_DIR / filename
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    dest.write_bytes(content)

    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)
    return user
