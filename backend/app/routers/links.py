from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import FamilyLink, HospitalLink, User
from ..schemas import (
    FamilyLinkCreate,
    FamilyLinkOut,
    HospitalLinkCreate,
    HospitalLinkOut,
)

router = APIRouter(prefix="/api/links", tags=["links"])


@router.get("/family", response_model=list[FamilyLinkOut])
def list_family(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(FamilyLink)
        .filter(FamilyLink.user_id == user.id)
        .order_by(FamilyLink.created_at.desc())
        .all()
    )


@router.post("/family", response_model=FamilyLinkOut)
def create_family(
    body: FamilyLinkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写家人姓名")
    row = FamilyLink(
        user_id=user.id,
        name=name,
        relation=(body.relation or "家人").strip() or "家人",
        phone=(body.phone or "").strip(),
        note=(body.note or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/family/{link_id}")
def delete_family(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(FamilyLink, link_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/hospitals", response_model=list[HospitalLinkOut])
def list_hospitals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(HospitalLink)
        .filter(HospitalLink.user_id == user.id)
        .order_by(HospitalLink.created_at.desc())
        .all()
    )


@router.post("/hospitals", response_model=HospitalLinkOut)
def create_hospital(
    body: HospitalLinkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = body.hospital_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写医院名称")
    row = HospitalLink(
        user_id=user.id,
        hospital_name=name,
        department=(body.department or "").strip(),
        doctor_name=(body.doctor_name or "").strip(),
        phone=(body.phone or "").strip(),
        address=(body.address or "").strip(),
        note=(body.note or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/hospitals/{link_id}")
def delete_hospital(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(HospitalLink, link_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
