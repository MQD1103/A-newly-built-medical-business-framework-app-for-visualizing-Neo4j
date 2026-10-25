"""AI 用药动作检测：鉴权、限流、调用适配、只保存步骤摘要。

原始影像只在内存中处理，立即丢弃；接口与日志都不输出图片内容。
"""

from __future__ import annotations

import os
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from .. import ai_service as service
from ..database import get_db
from ..deps import get_current_user
from ..models import Lesson, MedicationCheck, User
from ..rate_limit import SlidingWindowLimiter
from ..schemas import (
    MedicationCheckListOut,
    MedicationCheckOut,
    MedicationStepOut,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])

try:
    _limit = int(os.getenv("AI_RATE_LIMIT", "12") or "12")
    _window = int(os.getenv("AI_RATE_WINDOW_SECONDS", "60") or "60")
except ValueError:
    _limit, _window = 12, 60
detection_limiter = SlidingWindowLimiter(_limit, _window)


def to_out(row: MedicationCheck) -> MedicationCheckOut:
    return MedicationCheckOut(
        id=row.id,
        user_id=row.user_id,
        lesson_id=row.lesson_id,
        status=row.status or "completed",
        provider=row.provider or "demo",
        mode=row.mode or "oral",
        steps=[
            MedicationStepOut(name=str(item.get("name") or ""), done=bool(item.get("done")))
            for item in service.steps_from_json(row.steps_json)
            if item.get("name")
        ],
        needs_retry=bool(row.needs_retry),
        message=row.message or "",
        image_size=int(row.image_size or 0),
        image_type=row.image_type or "",
        created_at=row.created_at,
        expires_at=row.expires_at,
        disclaimer=service.DISCLAIMER,
    )


def _provider_name() -> str:
    return "http" if os.getenv("AI_DETECTOR_URL", "").strip() else "demo"


@router.post("/medication-checks", response_model=MedicationCheckOut)
def analyze_medication(
    file: UploadFile = File(...),
    lesson_id: int | None = Form(default=None),
    mode: str = Form(default="oral"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mode = (mode or "oral").strip().lower()
    if mode not in ("oral", "inhale"):
        raise HTTPException(status_code=400, detail="请选择用药方式：口服或吸入")

    key = f"ai:medication:{user.id}"
    wait = detection_limiter.retry_after(key)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"检测过于频繁，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )
    detection_limiter.hit(key)

    max_bytes = service.image_max_bytes()
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="图片过大，请压缩后重试")
    image_type = (file.content_type or "").split(";")[0].strip().lower()
    try:
        service.validate_image(data, image_type)
    except service.DetectionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    lesson = None
    if lesson_id is not None:
        lesson = db.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="课时不存在")

    current = service.now()
    try:
        steps, needs_retry, message, provider = service.detect(
            data, image_type, lesson_id, mode
        )
    except service.DetectionError as exc:
        # 失败也留一条脱敏摘要，便于用户回看“这次为什么失败”，不保存图片
        failed = MedicationCheck(
            user_id=user.id,
            lesson_id=lesson_id,
            status="failed",
            provider=_provider_name(),
            mode=mode,
            steps_json="[]",
            needs_retry=True,
            message=exc.message,
            image_size=len(data),
            image_type=image_type,
            created_at=current,
            expires_at=current + timedelta(days=service.retention_days()),
        )
        db.add(failed)
        service.prune_expired(db, current)
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    row = MedicationCheck(
        user_id=user.id,
        lesson_id=lesson_id,
        status="completed",
        provider=provider,
        mode=mode,
        steps_json=service.steps_to_json(steps),
        needs_retry=needs_retry,
        message=message,
        image_size=len(data),
        image_type=image_type,
        created_at=current,
        expires_at=current + timedelta(days=service.retention_days()),
    )
    db.add(row)
    service.prune_expired(db, current)
    db.commit()
    db.refresh(row)
    return to_out(row)


@router.get("/medication-checks", response_model=MedicationCheckListOut)
def list_medication_checks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service.prune_expired(db)
    db.commit()
    query = db.query(MedicationCheck).filter(MedicationCheck.user_id == user.id)
    total = query.count()
    rows = (
        query.order_by(MedicationCheck.created_at.desc(), MedicationCheck.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return MedicationCheckListOut(
        items=[to_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        retention_days=service.retention_days(),
        disclaimer=service.DISCLAIMER,
    )


@router.get("/medication-checks/{check_id}", response_model=MedicationCheckOut)
def get_medication_check(
    check_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(MedicationCheck, check_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="检测记录不存在")
    return to_out(row)


@router.delete("/medication-checks/{check_id}")
def delete_medication_check(
    check_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(MedicationCheck, check_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="检测记录不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
