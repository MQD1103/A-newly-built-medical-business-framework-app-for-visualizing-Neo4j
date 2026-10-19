"""商城健康服务商品：目录、下单与购买记录。

下单/支付/退款逻辑在 mall_service；这里保留旧接口并补充服务管理字段。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import mall_service as mall
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import ServiceProduct, ServicePurchase, User
from ..schemas import (
    ServiceProductCreate,
    ServiceProductOut,
    ServiceProductUpdate,
    ServicePurchaseOut,
)

router = APIRouter(prefix="/api/service-products", tags=["service-products"])


def owned_ids(db: Session, user: User) -> set[int]:
    return mall.accessible_service_ids(db, user)


def to_out(
    s: ServiceProduct,
    owned: set[int] | None = None,
    expires_at: object | None = None,
) -> ServiceProductOut:
    return ServiceProductOut(
        id=s.id,
        name=s.name,
        category=s.category or "健康服务",
        description=s.description or "",
        price=float(s.price if s.price is not None else 9.9),
        cover_url=(s.cover_url or "").strip(),
        unit_label=(s.unit_label or "单次").strip() or "单次",
        owned=True if owned is None else s.id in owned,
        tagline=s.tagline or "",
        original_price=(
            float(s.original_price) if s.original_price is not None else None
        ),
        status=s.status or "on",
        sort_order=int(s.sort_order or 0),
        valid_days=int(s.valid_days or 0),
        expires_at=expires_at,
    )


@router.get("", response_model=list[ServiceProductOut])
def list_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ServiceProduct)
    if user.role != "admin":
        query = query.filter(ServiceProduct.status == "on")
    items = query.order_by(ServiceProduct.sort_order, ServiceProduct.id).all()
    owned = owned_ids(db, user)
    result: list[ServiceProductOut] = []
    for item in items:
        expiry = None
        if item.id in owned:
            _, expiry, _ = mall.service_access_info(db, user, item)
        result.append(to_out(item, owned, expiry))
    return result


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
        tagline=(body.tagline or "").strip(),
        original_price=body.original_price,
        status=body.status or "on",
        sort_order=int(body.sort_order or 0),
        valid_days=int(body.valid_days or 0),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return to_out(item, owned_ids(db, user))


@router.patch("/{service_id}", response_model=ServiceProductOut)
def update_product(
    service_id: int,
    body: ServiceProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    item = db.get(ServiceProduct, service_id)
    if not item:
        raise HTTPException(status_code=404, detail="服务不存在")
    data = body.model_dump(exclude_unset=True)
    if "original_price" in data and data["original_price"] is None:
        item.original_price = None
        data.pop("original_price")
    for field, value in data.items():
        if field in ("cover_url", "tagline", "unit_label") and value is not None:
            value = value.strip()
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return to_out(item, owned_ids(db, user))


@router.get("/{service_id}", response_model=ServiceProductOut)
def get_product(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(ServiceProduct, service_id)
    if not item:
        raise HTTPException(status_code=404, detail="服务不存在")
    owned = owned_ids(db, user)
    expiry = (
        mall.service_access_info(db, user, item)[1] if item.id in owned else None
    )
    return to_out(item, owned, expiry)


@router.post("/{service_id}/purchase", response_model=ServicePurchaseOut)
def purchase_service(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """兼容旧前端的「确认即支付」：内部走完整订单 → 模拟支付。"""
    try:
        order = mall.create_service_order(db, user, service_id, channel="mock")
        if order.status == "pending":
            order = mall.pay_service_order(
                db, order, channel="mock", transaction_id="LEGACY"
            )
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    product = db.get(ServiceProduct, order.service_id)
    owned = owned_ids(db, user)
    expiry = (
        mall.service_access_info(db, user, product)[1] if product else None
    )
    return ServicePurchaseOut(
        id=order.id,
        service_id=order.service_id,
        service_name=product.name if product else "",
        amount=float(order.amount or 0),
        channel=order.channel or "mock",
        status=order.status,
        created_at=order.created_at,
        service=to_out(product, owned, expiry) if product else None,
        order_no=order.order_no or "",
        quantity=int(order.quantity or 1),
        unit_price=float(order.unit_price or 0),
        original_amount=float(order.original_amount or 0),
        discount_amount=float(order.discount_amount or 0),
        order_type=order.order_type or "normal",
        transaction_id=order.transaction_id or "",
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        valid_until=order.valid_until,
        refund_amount=float(order.refund_amount or 0),
        refunded_at=order.refunded_at,
        refund_reason=order.refund_reason or "",
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
        .limit(200)
        .all()
    )
    owned = owned_ids(db, user)
    result: list[ServicePurchaseOut] = []
    for order in rows:
        product = db.get(ServiceProduct, order.service_id)
        expiry = (
            mall.service_access_info(db, user, product)[1] if product else None
        )
        result.append(
            ServicePurchaseOut(
                id=order.id,
                service_id=order.service_id,
                service_name=product.name if product else "",
                amount=float(order.amount or 0),
                channel=order.channel or "mock",
                status=order.status or "paid",
                created_at=order.created_at,
                service=to_out(product, owned, expiry) if product else None,
                order_no=order.order_no or "",
                quantity=int(order.quantity or 1),
                unit_price=float(order.unit_price or 0),
                original_amount=float(order.original_amount or 0),
                discount_amount=float(order.discount_amount or 0),
                order_type=order.order_type or "normal",
                transaction_id=order.transaction_id or "",
                expires_at=order.expires_at,
                paid_at=order.paid_at,
                valid_until=order.valid_until,
                refund_amount=float(order.refund_amount or 0),
                refunded_at=order.refunded_at,
                refund_reason=order.refund_reason or "",
            )
        )
    return result
