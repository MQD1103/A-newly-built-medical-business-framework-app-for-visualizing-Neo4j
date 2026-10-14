from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import ServiceEntitlement, ServiceProduct, ServicePurchase, User
from ..schemas import ServiceProductCreate, ServiceProductOut, ServicePurchaseOut

router = APIRouter(prefix="/api/service-products", tags=["service-products"])


def owned_ids(db: Session, user: User) -> set[int]:
    if user.role == "admin":
        return {s.id for s in db.query(ServiceProduct.id).all()}
    return {
        e.service_id
        for e in db.query(ServiceEntitlement)
        .filter(ServiceEntitlement.user_id == user.id)
        .all()
    }


def to_out(s: ServiceProduct, owned: set[int] | None = None) -> ServiceProductOut:
    return ServiceProductOut(
        id=s.id,
        name=s.name,
        category=s.category or "健康服务",
        description=s.description or "",
        price=float(s.price if s.price is not None else 9.9),
        cover_url=(s.cover_url or "").strip(),
        unit_label=(s.unit_label or "单次").strip() or "单次",
        owned=True if owned is None else s.id in owned,
    )


@router.get("", response_model=list[ServiceProductOut])
def list_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned = owned_ids(db, user)
    items = db.query(ServiceProduct).order_by(ServiceProduct.id).all()
    return [to_out(s, owned) for s in items]


@router.post("", response_model=ServiceProductOut)
def create_product(
    body: ServiceProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    item = ServiceProduct(
        name=body.name,
        category=body.category or "健康服务",
        description=body.description,
        price=float(body.price if body.price is not None else 9.9),
        cover_url=(body.cover_url or "").strip(),
        unit_label=(body.unit_label or "单次").strip() or "单次",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return to_out(item, owned_ids(db, user))


@router.post("/{service_id}/purchase", response_model=ServicePurchaseOut)
def purchase_service(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """模拟支付开通服务。"""
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员无需购买，已默认可查看全部服务")

    product = db.get(ServiceProduct, service_id)
    if not product:
        raise HTTPException(status_code=404, detail="服务不存在")

    owned = owned_ids(db, user)
    if service_id in owned:
        raise HTTPException(status_code=400, detail="已开通该服务，无需重复购买")

    amount = float(product.price if product.price is not None else 9.9)
    purchase = ServicePurchase(
        user_id=user.id,
        service_id=product.id,
        amount=amount,
        channel="mock",
        status="paid",
    )
    db.add(purchase)
    db.add(ServiceEntitlement(user_id=user.id, service_id=product.id))
    db.commit()
    db.refresh(purchase)
    owned = owned_ids(db, user)
    return ServicePurchaseOut(
        id=purchase.id,
        service_id=product.id,
        service_name=product.name,
        amount=amount,
        channel=purchase.channel,
        status=purchase.status,
        created_at=purchase.created_at,
        service=to_out(product, owned),
    )


@router.get("/purchases/mine", response_model=list[ServicePurchaseOut])
def my_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(ServicePurchase)
        .filter(ServicePurchase.user_id == user.id)
        .order_by(ServicePurchase.created_at.desc())
        .limit(100)
        .all()
    )
    owned = owned_ids(db, user)
    return [
        ServicePurchaseOut(
            id=p.id,
            service_id=p.service_id,
            service_name=p.service.name if p.service else "",
            amount=float(p.amount),
            channel=p.channel,
            status=p.status,
            created_at=p.created_at,
            service=to_out(p.service, owned) if p.service else None,
        )
        for p in rows
    ]
