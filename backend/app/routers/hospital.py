"""医院对接：合作医院、用户授权、只读资料、照护者授权。

安全边界：
- 所有接口都要登录；用户只能读自己的资料，或患者明确授权的照护者读取。
- 医院资料全程只读，不提供修改病历、开药、改医嘱的接口。
- 医院地址与 Token 只在环境变量里，不下发前端、不写日志。
"""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import hospital_service as service
from .. import notification_service
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    HospitalAuthorization,
    HospitalCaregiverGrant,
    HospitalPartner,
    HospitalRecord,
    HospitalReminderLink,
    Reminder,
    User,
)
from ..rate_limit import SlidingWindowLimiter
from ..schemas import (
    HospitalAuthorizationCreate,
    HospitalAuthorizationOut,
    HospitalCaregiverCreate,
    HospitalCaregiverOut,
    HospitalCaregiversOut,
    HospitalPartnerCreate,
    HospitalPartnerOut,
    HospitalPartnerUpdate,
    HospitalRecordOut,
    HospitalReminderCreate,
    HospitalReminderOut,
    HospitalSyncOut,
)

router = APIRouter(prefix="/api/hospital", tags=["hospital"])

try:
    _sync_limit = int(os.getenv("HOSPITAL_SYNC_LIMIT", "6") or "6")
    _sync_window = int(os.getenv("HOSPITAL_SYNC_WINDOW_SECONDS", "300") or "300")
except ValueError:
    _sync_limit, _sync_window = 6, 300
sync_limiter = SlidingWindowLimiter(_sync_limit, _sync_window)


def partner_out(row: HospitalPartner) -> HospitalPartnerOut:
    return HospitalPartnerOut(
        id=row.id,
        code=row.code,
        name=row.name,
        department=row.department or "",
        status=row.status or "enabled",
        mode=row.mode or service.MODE_DEMO,
        contact=row.contact or "",
        note=row.note or "",
    )


def auth_out(row: HospitalAuthorization) -> HospitalAuthorizationOut:
    return HospitalAuthorizationOut(
        id=row.id,
        partner_id=row.partner_id,
        partner_name=row.partner.name if row.partner else "",
        patient_ref_masked=service.mask_patient_ref(row.patient_ref),
        scopes=[s for s in (row.scopes or "").split(",") if s],
        status=service.authorization_status(row),
        authorized_at=row.authorized_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def grant_out(row: HospitalCaregiverGrant) -> HospitalCaregiverOut:
    return HospitalCaregiverOut(
        id=row.id,
        patient_user_id=row.patient_user_id,
        patient_name=row.patient.full_name if row.patient else "",
        caregiver_user_id=row.caregiver_user_id,
        caregiver_name=row.caregiver.full_name if row.caregiver else "",
        relation=row.relation or "照护者",
        status=row.status or "active",
        granted_at=row.granted_at,
        revoked_at=row.revoked_at,
    )


def record_out(row: HospitalRecord) -> HospitalRecordOut:
    return HospitalRecordOut(
        id=row.id,
        partner_id=row.partner_id,
        partner_name=row.partner.name if row.partner else "",
        record_type=row.record_type,
        title=row.title,
        content=row.content or "",
        doctor_name=row.doctor_name or "",
        department=row.department or "",
        occurred_at=row.occurred_at,
        fetched_at=row.fetched_at,
    )


def resolve_patient(db: Session, viewer: User, patient_id: int | None) -> User:
    """本人，或持有有效照护授权的用户。"""
    if patient_id is None or patient_id == viewer.id:
        return viewer
    patient = db.get(User, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    grant = (
        db.query(HospitalCaregiverGrant)
        .filter(
            HospitalCaregiverGrant.patient_user_id == patient.id,
            HospitalCaregiverGrant.caregiver_user_id == viewer.id,
            HospitalCaregiverGrant.status == "active",
        )
        .first()
    )
    if not grant:
        raise HTTPException(status_code=403, detail="未获得该患者的查看授权")
    return patient


def require_active_auth(db: Session, user_id: int, partner_id: int) -> None:
    auths = service.active_authorizations(db, user_id)
    if not any(auth.partner_id == partner_id for auth in auths):
        raise HTTPException(status_code=403, detail="医院授权已失效，请重新授权")


# ---------- 合作医院 ----------


@router.get("/partners", response_model=list[HospitalPartnerOut])
def list_partners(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(HospitalPartner)
        .filter(HospitalPartner.status == "enabled")
        .order_by(HospitalPartner.id.asc())
        .all()
    )
    return [partner_out(row) for row in rows]


@router.get("/admin/partners", response_model=list[HospitalPartnerOut])
def admin_list_partners(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    rows = db.query(HospitalPartner).order_by(HospitalPartner.id.asc()).all()
    return [partner_out(row) for row in rows]


@router.post("/admin/partners", response_model=HospitalPartnerOut)
def admin_create_partner(
    body: HospitalPartnerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    row = HospitalPartner(
        code=body.code.strip(),
        name=body.name.strip(),
        department=body.department.strip(),
        mode=body.mode,
        status=body.status,
        contact=body.contact.strip(),
        note=body.note.strip(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="医院编码已存在")
    db.refresh(row)
    return partner_out(row)


@router.patch("/admin/partners/{partner_id}", response_model=HospitalPartnerOut)
def admin_update_partner(
    partner_id: int,
    body: HospitalPartnerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    row = db.get(HospitalPartner, partner_id)
    if not row:
        raise HTTPException(status_code=404, detail="合作医院不存在")
    if body.name is not None:
        row.name = body.name.strip()
    if body.department is not None:
        row.department = body.department.strip()
    if body.mode is not None:
        row.mode = body.mode
    if body.status is not None:
        row.status = body.status
    if body.contact is not None:
        row.contact = body.contact.strip()
    if body.note is not None:
        row.note = body.note.strip()
    db.commit()
    db.refresh(row)
    return partner_out(row)


# ---------- 用户授权 ----------


@router.get("/authorizations", response_model=list[HospitalAuthorizationOut])
def list_authorizations(
    patient_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = resolve_patient(db, user, patient_id)
    rows = (
        db.query(HospitalAuthorization)
        .filter(HospitalAuthorization.user_id == patient.id)
        .order_by(HospitalAuthorization.authorized_at.desc())
        .all()
    )
    return [auth_out(row) for row in rows]


@router.post("/authorizations", response_model=HospitalAuthorizationOut)
def create_authorization(
    body: HospitalAuthorizationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.consent:
        raise HTTPException(status_code=400, detail="请先确认授权后再提交")
    partner = db.get(HospitalPartner, body.partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="合作医院不存在")
    if (partner.status or "enabled") != "enabled":
        raise HTTPException(status_code=400, detail="该医院尚未开通")
    patient_ref = body.patient_ref.strip()
    if len(patient_ref) < 4:
        raise HTTPException(status_code=400, detail="请填写医院患者标识")

    row = (
        db.query(HospitalAuthorization)
        .filter(
            HospitalAuthorization.user_id == user.id,
            HospitalAuthorization.partner_id == partner.id,
        )
        .first()
    )
    current = service.now()
    if row is None:
        row = HospitalAuthorization(
            user_id=user.id,
            partner_id=partner.id,
            patient_ref=patient_ref,
            scopes="advice,condition,record",
            status="active",
            authorized_at=current,
            created_at=current,
        )
        db.add(row)
    else:
        row.patient_ref = patient_ref
        row.scopes = "advice,condition,record"
        row.status = "active"
        row.authorized_at = current
        row.revoked_at = None
    db.commit()
    db.refresh(row)
    return auth_out(row)


@router.delete("/authorizations/{auth_id}", response_model=HospitalAuthorizationOut)
def revoke_authorization(
    auth_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(HospitalAuthorization, auth_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="授权记录不存在")
    row.status = "revoked"
    row.revoked_at = service.now()
    db.commit()
    db.refresh(row)
    return auth_out(row)


@router.post("/authorizations/{auth_id}/sync", response_model=HospitalSyncOut)
def sync_authorization(
    auth_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(HospitalAuthorization, auth_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="授权记录不存在")

    key = f"hospital:sync:{user.id}"
    wait = sync_limiter.retry_after(key)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"同步过于频繁，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )
    sync_limiter.hit(key)

    try:
        added, updated, total = service.sync_authorization(db, row)
    except service.HospitalError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    db.commit()
    return HospitalSyncOut(
        added=added,
        updated=updated,
        total=total,
        fetched_at=service.now(),
    )


# ---------- 只读资料 ----------


@router.get("/records", response_model=list[HospitalRecordOut])
def list_records(
    patient_id: int | None = Query(default=None),
    record_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = resolve_patient(db, user, patient_id)
    if record_type is not None:
        if record_type not in service.RECORD_TYPES:
            raise HTTPException(status_code=400, detail="资料类型不合法")
    partner_ids = [a.partner_id for a in service.active_authorizations(db, patient.id)]
    if not partner_ids:
        return []
    query = db.query(HospitalRecord).filter(
        HospitalRecord.user_id == patient.id,
        HospitalRecord.partner_id.in_(partner_ids),
    )
    if record_type:
        query = query.filter(HospitalRecord.record_type == record_type)
    rows = (
        query.order_by(
            HospitalRecord.occurred_at.desc(),
            HospitalRecord.id.desc(),
        ).all()
    )
    return [record_out(row) for row in rows]


@router.get("/records/{record_id}", response_model=HospitalRecordOut)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(HospitalRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    resolve_patient(db, user, row.user_id)
    require_active_auth(db, row.user_id, row.partner_id)
    return record_out(row)


@router.post("/records/{record_id}/reminder", response_model=HospitalReminderOut)
def create_reminder_from_record(
    record_id: int,
    body: HospitalReminderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(HospitalRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    if row.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能为自己的嘱托设置提醒")
    if row.record_type != "advice":
        raise HTTPException(status_code=400, detail="只有医生嘱托可以转为提醒")
    require_active_auth(db, user.id, row.partner_id)

    title = (body.title or row.title).strip()[:200]
    if not title:
        raise HTTPException(status_code=400, detail="请填写提醒标题")
    partner_name = row.partner.name if row.partner else "医院"
    content = (body.content or "").strip()
    if not content:
        content = f"来自{partner_name}的医生嘱托：\n{row.content or ''}"

    reminder = Reminder(
        course_id=None,
        title=title,
        content=content,
        due_at=body.due_at,
        external_url="",
        creator_id=user.id,
        source="user",
    )
    db.add(reminder)
    db.flush()
    db.add(
        HospitalReminderLink(
            user_id=user.id,
            record_id=row.id,
            reminder_id=reminder.id,
        )
    )
    notification_service.sync_reminder_notifications(db, reminder)
    db.commit()
    db.refresh(reminder)
    return HospitalReminderOut(
        reminder_id=reminder.id,
        record_id=row.id,
        title=reminder.title,
        due_at=reminder.due_at,
    )


# ---------- 照护者授权 ----------


@router.get("/caregivers", response_model=HospitalCaregiversOut)
def list_caregivers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    granted = (
        db.query(HospitalCaregiverGrant)
        .filter(HospitalCaregiverGrant.patient_user_id == user.id)
        .order_by(HospitalCaregiverGrant.id.desc())
        .all()
    )
    received = (
        db.query(HospitalCaregiverGrant)
        .filter(
            HospitalCaregiverGrant.caregiver_user_id == user.id,
            HospitalCaregiverGrant.status == "active",
        )
        .order_by(HospitalCaregiverGrant.id.desc())
        .all()
    )
    return HospitalCaregiversOut(
        granted=[grant_out(row) for row in granted],
        received=[grant_out(row) for row in received],
    )


@router.post("/caregivers", response_model=HospitalCaregiverOut)
def grant_caregiver(
    body: HospitalCaregiverCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    caregiver = (
        db.query(User)
        .filter(User.username == body.caregiver_username.strip())
        .first()
    )
    if not caregiver:
        raise HTTPException(status_code=404, detail="该用户不存在")
    if caregiver.id == user.id:
        raise HTTPException(status_code=400, detail="不能授权给自己")

    row = (
        db.query(HospitalCaregiverGrant)
        .filter(
            HospitalCaregiverGrant.patient_user_id == user.id,
            HospitalCaregiverGrant.caregiver_user_id == caregiver.id,
        )
        .first()
    )
    current = service.now()
    relation = (body.relation or "照护者").strip()[:40] or "照护者"
    if row is None:
        row = HospitalCaregiverGrant(
            patient_user_id=user.id,
            caregiver_user_id=caregiver.id,
            relation=relation,
            status="active",
            granted_at=current,
        )
        db.add(row)
    else:
        row.relation = relation
        row.status = "active"
        row.granted_at = current
        row.revoked_at = None
    db.commit()
    db.refresh(row)
    return grant_out(row)


@router.delete("/caregivers/{grant_id}", response_model=HospitalCaregiverOut)
def revoke_caregiver(
    grant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(HospitalCaregiverGrant, grant_id)
    if not row or user.id not in (row.patient_user_id, row.caregiver_user_id):
        raise HTTPException(status_code=404, detail="授权记录不存在")
    row.status = "revoked"
    row.revoked_at = service.now()
    db.commit()
    db.refresh(row)
    return grant_out(row)
