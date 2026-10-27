"""个人健康档案：诊断、肺功能分级、用药史、紧急联系人与主治医生。

每个用户一条记录，本人可读写；管理员可按 user_id 查看，便于管理端核对。
档案仅用于就诊时快速出示与自我管理，不构成诊断结论。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import HealthProfile, User
from ..schemas import HealthProfileIn, HealthProfileOut

router = APIRouter(prefix="/api/health-profile", tags=["health-profile"])

# 计算完整度用的字段与中文名（顺序即缺失项提示顺序）
CHECK_FIELDS: list[tuple[str, str]] = [
    ("sex", "性别"),
    ("birth_year", "出生年份"),
    ("height_cm", "身高"),
    ("weight_kg", "体重"),
    ("diagnosis", "诊断"),
    ("copd_grade", "肺功能分级"),
    ("fev1_percent", "FEV1 占预计值"),
    ("current_meds", "当前用药"),
    ("allergies", "过敏史"),
    ("past_history", "既往病史"),
    ("emergency_name", "紧急联系人"),
    ("emergency_phone", "紧急联系人电话"),
    ("doctor_name", "主治医生"),
    ("doctor_hospital", "就诊医院"),
]


def _score(profile: HealthProfile) -> tuple[int, list[str]]:
    filled = 0
    missing: list[str] = []
    for field, label in CHECK_FIELDS:
        value = (getattr(profile, field) or "").strip()
        if value:
            filled += 1
        else:
            missing.append(label)
    total = len(CHECK_FIELDS)
    return round(filled * 100 / total), missing


def _out(profile: HealthProfile, user: User) -> HealthProfileOut:
    completeness, missing = _score(profile)
    data = HealthProfileOut.model_validate(profile)
    data.full_name = user.full_name
    data.username = user.username
    data.completeness = completeness
    data.missing = missing
    return data


def _empty(user: User) -> HealthProfileOut:
    """还没有档案时返回空壳，前端一次渲染即可，不必区分 null。"""
    data = HealthProfileOut()
    data.full_name = user.full_name
    data.username = user.username
    data.completeness = 0
    data.missing = [label for _, label in CHECK_FIELDS]
    return data


@router.get("", response_model=HealthProfileOut)
def read_profile(
    user_id: int | None = Query(default=None, description="管理员可指定查看某用户"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = user
    if user_id is not None and user_id != user.id:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="无权查看他人档案")
        found = db.get(User, user_id)
        if not found:
            raise HTTPException(status_code=404, detail="用户不存在")
        target = found

    profile = (
        db.query(HealthProfile).filter(HealthProfile.user_id == target.id).first()
    )
    if not profile:
        return _empty(target)
    return _out(profile, target)


@router.put("", response_model=HealthProfileOut)
def save_profile(
    body: HealthProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    if not profile:
        profile = HealthProfile(user_id=user.id)
        db.add(profile)

    for field in HealthProfileIn.model_fields:
        value = getattr(body, field)
        setattr(profile, field, (value or "").strip())

    db.commit()
    db.refresh(profile)
    return _out(profile, user)
