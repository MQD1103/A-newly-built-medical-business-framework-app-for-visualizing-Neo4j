"""症状日记：每日记录咳嗽 / 气短 / 痰量，提示是否较前明显加重。

只做自我观察与就医提醒，不提供诊断或用药建议。
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import SymptomEntry, User
from ..schemas import SymptomDiaryOut, SymptomEntryIn, SymptomEntryOut

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"])

DISCLAIMER = (
    "症状日记仅用于自我观察，不构成诊断或用药建议；"
    "如出现明显气短、胸痛、咯血或症状持续加重，请及时就医。"
)

SYMPTOM_NAMES = {"cough": "咳嗽", "dyspnea": "气短", "sputum": "痰量"}


def entry_total(entry: SymptomEntry) -> int:
    return int(entry.cough or 0) + int(entry.dyspnea or 0) + int(entry.sputum or 0)


def entry_warning(entry: SymptomEntry, previous: SymptomEntry | None) -> tuple[bool, str]:
    """单条记录是否提示加重：任一项达重度，或总分较上次上升 ≥3。"""
    reasons: list[str] = []
    for field, label in SYMPTOM_NAMES.items():
        if int(getattr(entry, field) or 0) >= 3:
            reasons.append(f"{label}达到重度")
    if previous is not None and entry_total(entry) - entry_total(previous) >= 3:
        reasons.append("总分较上次明显上升")
    if not reasons:
        return False, ""
    return True, "、".join(reasons) + "，建议联系医生或及时就医。"


def entry_out(entry: SymptomEntry, previous: SymptomEntry | None) -> SymptomEntryOut:
    warning, warning_text = entry_warning(entry, previous)
    return SymptomEntryOut(
        id=entry.id,
        record_date=entry.record_date,
        cough=int(entry.cough or 0),
        dyspnea=int(entry.dyspnea or 0),
        sputum=int(entry.sputum or 0),
        note=entry.note or "",
        total=entry_total(entry),
        warning=warning,
        warning_text=warning_text,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("", response_model=SymptomDiaryOut)
def get_diary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = date.today() - timedelta(days=days - 1)
    rows = (
        db.query(SymptomEntry)
        .filter(SymptomEntry.user_id == user.id, SymptomEntry.record_date >= since)
        .order_by(SymptomEntry.record_date.desc(), SymptomEntry.id.desc())
        .all()
    )
    # rows 为倒序，previous 指「更早一条」
    items: list[SymptomEntryOut] = []
    for index, row in enumerate(rows):
        previous = rows[index + 1] if index + 1 < len(rows) else None
        items.append(entry_out(row, previous))

    warning = bool(items) and items[0].warning
    warning_text = items[0].warning_text if warning else ""
    return SymptomDiaryOut(
        items=items,
        warning=warning,
        warning_text=warning_text,
        disclaimer=DISCLAIMER,
    )


@router.post("", response_model=SymptomEntryOut)
def upsert_entry(
    body: SymptomEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """同一天再次提交视为更新，不产生重复记录。"""
    record_date = body.record_date or date.today()
    if record_date > date.today():
        raise HTTPException(status_code=400, detail="不能记录未来日期的症状")

    entry = (
        db.query(SymptomEntry)
        .filter(
            SymptomEntry.user_id == user.id,
            SymptomEntry.record_date == record_date,
        )
        .first()
    )
    if entry is None:
        entry = SymptomEntry(user_id=user.id, record_date=record_date)
        db.add(entry)
    entry.cough = body.cough
    entry.dyspnea = body.dyspnea
    entry.sputum = body.sputum
    entry.note = (body.note or "").strip()
    entry.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)

    previous = (
        db.query(SymptomEntry)
        .filter(
            SymptomEntry.user_id == user.id,
            SymptomEntry.record_date < record_date,
        )
        .order_by(SymptomEntry.record_date.desc())
        .first()
    )
    return entry_out(entry, previous)


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = db.get(SymptomEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(entry)
    db.commit()
    return {"ok": True}
