"""用户协议 / 隐私政策的展示与同意记录。

- 协议列表与全文：公开接口（登录页也要能看）。
- 同意记录：登录后可用；按「协议类型 + 版本」留痕，历史记录不删除。
- 前端在登录后调用 consents/me，若 pending 非空则弹出确认弹窗。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agreements import AGREEMENTS, get_agreement
from ..database import get_db
from ..deps import get_current_user
from ..models import User, UserConsent
from ..schemas import AgreementOut, ConsentCreate, ConsentOut, ConsentStatusOut

router = APIRouter(tags=["agreements"])


@router.get("/api/agreements", response_model=list[AgreementOut])
def list_agreements():
    """协议目录（不含全文，全文走详情接口）。"""
    return [
        AgreementOut(
            agreement_type=a.agreement_type,
            title=a.title,
            version=a.version,
            effective_date=a.effective_date,
            summary=a.summary,
            content=None,
        )
        for a in AGREEMENTS.values()
    ]


@router.get("/api/agreements/{agreement_type}", response_model=AgreementOut)
def get_agreement_detail(agreement_type: str):
    """协议全文（Markdown 文本），登录页可直接访问。"""
    agreement = get_agreement(agreement_type)
    if agreement is None:
        raise HTTPException(status_code=404, detail="协议不存在")
    return AgreementOut(
        agreement_type=agreement.agreement_type,
        title=agreement.title,
        version=agreement.version,
        effective_date=agreement.effective_date,
        summary=agreement.summary,
        content=agreement.content,
    )


@router.get("/api/consents/me", response_model=ConsentStatusOut)
def my_consents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(UserConsent)
        .filter(UserConsent.user_id == user.id)
        .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
        .all()
    )
    accepted = {(r.agreement_type, r.version) for r in rows}
    pending = [
        a_type
        for a_type, agreement in AGREEMENTS.items()
        if (a_type, agreement.version) not in accepted
    ]
    return ConsentStatusOut(
        consents=[ConsentOut.model_validate(r) for r in rows],
        pending=pending,
    )


@router.post("/api/consent", response_model=ConsentOut)
def accept_agreement(
    body: ConsentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """记录一条同意；重复同意同一版本保持幂等，返回已有记录。"""
    agreement = get_agreement(body.agreement_type)
    if agreement is None:
        raise HTTPException(status_code=404, detail="协议不存在")
    version = body.version or agreement.version
    if version != agreement.version:
        raise HTTPException(status_code=400, detail="协议版本不存在或已过期")

    existing = (
        db.query(UserConsent)
        .filter(
            UserConsent.user_id == user.id,
            UserConsent.agreement_type == body.agreement_type,
            UserConsent.version == version,
        )
        .first()
    )
    if existing:
        return ConsentOut.model_validate(existing)

    record = UserConsent(
        user_id=user.id,
        agreement_type=body.agreement_type,
        version=version,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ConsentOut.model_validate(record)
