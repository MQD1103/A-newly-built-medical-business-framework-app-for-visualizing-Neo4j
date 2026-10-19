"""商城 API：统一商品目录、订单、支付、退款、团购名额与我的课程。

旧接口 /api/courses、/api/service-products 继续可用；本模块提供完整商城流程。
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import mall_service as mall
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    Course,
    CoursePurchase,
    ServiceProduct,
    ServicePurchase,
    User,
)
from ..schemas import (
    CourseProgressOut,
    MallEntitlementsOut,
    MallMyCourseOut,
    MallOrderCreate,
    MallOrderListOut,
    MallOrderOut,
    MallPayIn,
    MallPaymentCallbackIn,
    MallProductDetailOut,
    MallProductListOut,
    MallRedeemIn,
    MallRedeemOut,
    MallRefundCheckOut,
    MallRefundIn,
    MallSummaryOut,
    ServiceProductOut,
)
from .courses import to_out as course_to_out
from .service_products import to_out as service_to_out

router = APIRouter(prefix="/api/mall", tags=["mall"])


# ---------- 通用 ----------


def _find_order(
    db: Session, order_no: str
) -> tuple[str, CoursePurchase | ServicePurchase] | None:
    order_no = (order_no or "").strip()
    if not order_no:
        return None
    course_order = (
        db.query(CoursePurchase)
        .filter(CoursePurchase.order_no == order_no)
        .first()
    )
    if course_order:
        return "course", course_order
    service_order = (
        db.query(ServicePurchase)
        .filter(ServicePurchase.order_no == order_no)
        .first()
    )
    if service_order:
        return "service", service_order
    return None


def _get_order(
    db: Session, order_no: str, user: User, allow_admin: bool = True
) -> tuple[str, CoursePurchase | ServicePurchase]:
    found = _find_order(db, order_no)
    if not found:
        raise HTTPException(status_code=404, detail="订单不存在")
    kind, order = found
    if order.user_id != user.id and not (allow_admin and user.role == "admin"):
        raise HTTPException(status_code=403, detail="无权查看该订单")
    return kind, order


def _order_out(
    db: Session, kind: str, order: CoursePurchase | ServicePurchase
) -> MallOrderOut:
    if kind == "course":
        return mall.course_order_out(db, order)
    return mall.service_order_out(db, order)


# ---------- 商品目录 ----------


@router.get("/products", response_model=MallProductListOut)
def list_products(
    product_type: str = Query(default="all", pattern="^(all|course|service)$"),
    category: str = "",
    q: str = "",
    include_off: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """商城统一商品列表：课程 + 健康服务。"""
    include_off = bool(include_off and user.role == "admin")
    keyword = (q or "").strip().lower()
    category = (category or "").strip()

    items: list = []

    if product_type in ("all", "course"):
        query = db.query(Course)
        if not include_off:
            query = query.filter(Course.status == "on")
        for course in query.order_by(Course.sort_order, Course.id).all():
            if category and category not in (course.path_label or "", course.semester or ""):
                continue
            if keyword and keyword not in " ".join(
                [
                    course.name or "",
                    course.description or "",
                    course.tagline or "",
                    course.path_label or "",
                ]
            ).lower():
                continue
            items.append((0, course.sort_order or 0, course.id, "course", course))

    if product_type in ("all", "service"):
        query = db.query(ServiceProduct)
        if not include_off:
            query = query.filter(ServiceProduct.status == "on")
        for service in query.order_by(ServiceProduct.sort_order, ServiceProduct.id).all():
            if category and category not in (
                service.category or "",
                service.tagline or "",
            ):
                continue
            if keyword and keyword not in " ".join(
                [
                    service.name or "",
                    service.description or "",
                    service.tagline or "",
                    service.category or "",
                ]
            ).lower():
                continue
            items.append((1, service.sort_order or 0, service.id, "service", service))

    items.sort(key=lambda row: (row[0], row[1], row[2]))
    result = []
    for _, _, _, kind, obj in items:
        if kind == "course":
            result.append(mall.course_product_out(db, obj, user))
        else:
            result.append(mall.service_product_out(db, obj, user))
    return MallProductListOut(items=result, total=len(result))


@router.get(
    "/products/{product_type}/{product_id}", response_model=MallProductDetailOut
)
def product_detail(
    product_type: str,
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if product_type == "course":
        course = db.get(Course, product_id)
        if not course:
            raise HTTPException(status_code=404, detail="课程不存在")
        owned, _, _ = mall.course_access_info(db, user, course)
        if (course.status or "on") != "on" and user.role != "admin" and not owned:
            raise HTTPException(status_code=404, detail="课程不存在或已下架")
        return mall.course_product_detail(db, course, user)
    if product_type == "service":
        service = db.get(ServiceProduct, product_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        owned, _, _ = mall.service_access_info(db, user, service)
        if (service.status or "on") != "on" and user.role != "admin" and not owned:
            raise HTTPException(status_code=404, detail="服务不存在或已下架")
        return mall.service_product_detail(db, service, user)
    raise HTTPException(status_code=400, detail="商品类型需为 course 或 service")


@router.get("/summary", response_model=MallSummaryOut)
def mall_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mall.expire_pending_orders(db)
    course_ids = mall.accessible_course_ids(db, user)
    service_ids = mall.accessible_service_ids(db, user)
    course_count = (
        db.query(Course).filter(Course.status == "on").count()
        if user.role != "admin"
        else db.query(Course).count()
    )
    service_count = (
        db.query(ServiceProduct).filter(ServiceProduct.status == "on").count()
        if user.role != "admin"
        else db.query(ServiceProduct).count()
    )
    pending = (
        db.query(CoursePurchase)
        .filter(
            CoursePurchase.user_id == user.id,
            CoursePurchase.status == "pending",
        )
        .count()
        + db.query(ServicePurchase)
        .filter(
            ServicePurchase.user_id == user.id,
            ServicePurchase.status == "pending",
        )
        .count()
    )
    paid = (
        db.query(CoursePurchase)
        .filter(
            CoursePurchase.user_id == user.id,
            CoursePurchase.status.in_(["paid", "partially_refunded"]),
        )
        .count()
        + db.query(ServicePurchase)
        .filter(
            ServicePurchase.user_id == user.id,
            ServicePurchase.status.in_(["paid", "partially_refunded"]),
        )
        .count()
    )
    return MallSummaryOut(
        course_count=course_count,
        service_count=service_count,
        owned_course_count=len(course_ids),
        owned_service_count=len(service_ids),
        pending_orders=pending,
        paid_orders=paid,
        refund_policy=mall.REFUND_POLICY,
    )


@router.get("/refund-policy")
def refund_policy():
    return {
        "policy": mall.REFUND_POLICY,
        "window_days": mall.REFUND_WINDOW_DAYS,
        "progress_limit": mall.REFUND_PROGRESS_LIMIT,
        "order_ttl_minutes": mall.ORDER_TTL_MINUTES,
        "auto_refund": os.getenv("MALL_AUTO_REFUND", "1").strip() != "0",
    }


# ---------- 我的课程 / 权益 ----------


@router.get("/my-courses", response_model=list[MallMyCourseOut])
def my_courses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned = mall.accessible_course_ids(db, user)
    courses = (
        db.query(Course)
        .filter(Course.id.in_(owned))
        .order_by(Course.sort_order, Course.id)
        .all()
        if owned
        else []
    )
    result: list[MallMyCourseOut] = []
    for course in courses:
        if (course.status or "on") != "on" and user.role != "admin":
            # 已购课程下架后仍可学习，但不下架课程不进「我的课程」以外的地方
            pass
        _, expires_at, source = mall.course_access_info(db, user, course)
        progress = mall.course_progress(db, user.id, course)
        result.append(
            MallMyCourseOut(
                course=course_to_out(db, course, owned, expires_at),
                source=source or "purchase",
                expires_at=expires_at,
                total_lessons=progress["total_lessons"],
                completed_lessons=progress["completed_lessons"],
                progress_percent=progress["percent"],
            )
        )
    return result


@router.get("/entitlements", response_model=MallEntitlementsOut)
def my_entitlements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    course_ids = mall.accessible_course_ids(db, user)
    courses = (
        db.query(Course)
        .filter(Course.id.in_(course_ids))
        .order_by(Course.sort_order, Course.id)
        .all()
        if course_ids
        else []
    )
    course_items = []
    for course in courses:
        _, expires_at, source = mall.course_access_info(db, user, course)
        progress = mall.course_progress(db, user.id, course)
        course_items.append(
            MallMyCourseOut(
                course=course_to_out(db, course, course_ids, expires_at),
                source=source or "purchase",
                expires_at=expires_at,
                total_lessons=progress["total_lessons"],
                completed_lessons=progress["completed_lessons"],
                progress_percent=progress["percent"],
            )
        )

    service_ids = mall.accessible_service_ids(db, user)
    services = (
        db.query(ServiceProduct)
        .filter(ServiceProduct.id.in_(service_ids))
        .order_by(ServiceProduct.sort_order, ServiceProduct.id)
        .all()
        if service_ids
        else []
    )
    service_items: list[ServiceProductOut] = []
    for service in services:
        _, expires_at, _ = mall.service_access_info(db, user, service)
        service_items.append(service_to_out(service, service_ids, expires_at))
    return MallEntitlementsOut(courses=course_items, services=service_items)


# ---------- 订单 ----------


@router.post("/orders", response_model=MallOrderOut)
def create_order(
    body: MallOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建待支付订单。学习人可与购买人不同；多人学习即团购/代买。"""
    try:
        if body.product_type == "course":
            order = mall.create_course_order(
                db,
                user,
                body.product_id,
                quantity=body.quantity,
                channel=body.channel,
                learners=body.learners,
                remark=body.remark,
            )
            return mall.course_order_out(db, order)
        if body.quantity != 1:
            raise HTTPException(status_code=400, detail="服务一次只能购买 1 份")
        order = mall.create_service_order(
            db, user, body.product_id, channel=body.channel, remark=body.remark
        )
        return mall.service_order_out(db, order)
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/orders/{order_no}/pay", response_model=MallOrderOut)
def pay_order(
    order_no: str,
    body: MallPayIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kind, order = _get_order(db, order_no, user, allow_admin=False)
    try:
        if kind == "course":
            order = mall.pay_course_order(
                db, order, channel=body.channel, transaction_id=body.transaction_id
            )
        else:
            order = mall.pay_service_order(
                db, order, channel=body.channel, transaction_id=body.transaction_id
            )
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _order_out(db, kind, order)


@router.post("/orders/{order_no}/cancel", response_model=MallOrderOut)
def cancel_order(
    order_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kind, order = _get_order(db, order_no, user, allow_admin=False)
    try:
        if kind == "course":
            order = mall.cancel_course_order(db, order)
        else:
            order = mall.cancel_service_order(db, order)
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _order_out(db, kind, order)


@router.get("/orders/mine", response_model=MallOrderListOut)
@router.get("/orders", response_model=MallOrderListOut)
def list_my_orders(
    status: str = "",
    product_type: str = Query(default="", pattern="^(|course|service)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mall.expire_pending_orders(db)
    rows: list[tuple[object, str, CoursePurchase | ServicePurchase]] = []
    if product_type in ("", "course"):
        course_query = db.query(CoursePurchase).filter(
            CoursePurchase.user_id == user.id
        )
        if status:
            course_query = course_query.filter(CoursePurchase.status == status)
        rows.extend(
            (order.created_at, "course", order) for order in course_query.all()
        )
    if product_type in ("", "service"):
        service_query = db.query(ServicePurchase).filter(
            ServicePurchase.user_id == user.id
        )
        if status:
            service_query = service_query.filter(ServicePurchase.status == status)
        rows.extend(
            (order.created_at, "service", order) for order in service_query.all()
        )
    rows.sort(key=lambda row: row[0], reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    selected = rows[start : start + page_size]
    return MallOrderListOut(
        items=[
            _order_out(db, kind, order) for _, kind, order in selected
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{order_no}", response_model=MallOrderOut)
def get_order(
    order_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kind, order = _get_order(db, order_no, user, allow_admin=True)
    return _order_out(db, kind, order)


@router.get("/orders/{order_no}/refund-check", response_model=MallRefundCheckOut)
def refund_check(
    order_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kind, order = _get_order(db, order_no, user, allow_admin=True)
    check = mall.refund_check(db, order)
    return MallRefundCheckOut(
        eligible=check["eligible"],
        reason=check["reason"],
        refund_amount=check["refund_amount"],
        within_window=check["within_window"],
        window_ends_at=check["window_ends_at"],
        progress_percent=check["progress_percent"],
        policy=check["policy"],
    )


@router.post("/orders/{order_no}/refund", response_model=MallOrderOut)
def refund_order(
    order_no: str,
    body: MallRefundIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kind, order = _get_order(db, order_no, user, allow_admin=False)
    try:
        mall.request_refund(db, order, reason=body.reason)
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _order_out(db, kind, order)


# ---------- 团购名额兑换 ----------


@router.post("/seats/redeem", response_model=MallRedeemOut)
def redeem_seat(
    body: MallRedeemIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        seat = mall.redeem_seat(db, user, body.activation_code)
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    order = seat.order
    course = db.get(Course, order.course_id) if order else None
    return MallRedeemOut(
        ok=True,
        course_id=order.course_id if order else 0,
        course_name=course.name if course else "",
        learner_name=seat.learner_name or user.full_name,
        expires_at=order.valid_until if order else None,
    )


# ---------- 支付回调（演示） ----------


@router.post("/payments/callback")
def payment_callback(
    body: MallPaymentCallbackIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """支付渠道回调。

    演示环境默认不校验签名；配置 MALL_PAYMENT_CALLBACK_TOKEN 后，
    回调方必须带 X-Payment-Token 请求头。生产接入真实支付时，
    应在此处校验渠道签名并核对金额。
    """
    expected = os.getenv("MALL_PAYMENT_CALLBACK_TOKEN", "").strip()
    if expected and request.headers.get("X-Payment-Token") != expected:
        raise HTTPException(status_code=403, detail="回调校验失败")

    found = _find_order(db, body.order_no)
    if not found:
        raise HTTPException(status_code=404, detail="订单不存在")
    kind, order = found

    if body.status == "failed":
        if order.status == "pending":
            if kind == "course":
                mall.cancel_course_order(db, order)
            else:
                mall.cancel_service_order(db, order)
        return {"ok": True, "order_no": order.order_no, "status": order.status}

    try:
        if kind == "course":
            mall.pay_course_order(
                db,
                order,
                channel=body.channel,
                transaction_id=body.transaction_id,
            )
        else:
            mall.pay_service_order(
                db,
                order,
                channel=body.channel,
                transaction_id=body.transaction_id,
            )
    except mall.MallError as exc:
        # 已支付等幂等场景不当作回调失败
        if order.status == "paid":
            return {
                "ok": True,
                "order_no": order.order_no,
                "status": order.status,
            }
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"ok": True, "order_no": order.order_no, "status": order.status}


# ---------- 管理员订单 ----------


@router.get("/admin/orders", response_model=MallOrderListOut)
def admin_list_orders(
    status: str = "",
    product_type: str = Query(default="", pattern="^(|course|service)$"),
    buyer_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    mall.expire_pending_orders(db)
    rows: list[tuple[object, str, CoursePurchase | ServicePurchase]] = []
    if product_type in ("", "course"):
        query = db.query(CoursePurchase)
        if status:
            query = query.filter(CoursePurchase.status == status)
        if buyer_id:
            query = query.filter(CoursePurchase.user_id == buyer_id)
        rows.extend((order.created_at, "course", order) for order in query.all())
    if product_type in ("", "service"):
        query = db.query(ServicePurchase)
        if status:
            query = query.filter(ServicePurchase.status == status)
        if buyer_id:
            query = query.filter(ServicePurchase.user_id == buyer_id)
        rows.extend((order.created_at, "service", order) for order in query.all())
    rows.sort(key=lambda row: row[0], reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    selected = rows[start : start + page_size]
    return MallOrderListOut(
        items=[_order_out(db, kind, order) for _, kind, order in selected],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/admin/orders/{order_no}/refund", response_model=MallOrderOut)
def admin_refund_order(
    order_no: str,
    body: MallRefundIn,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    found = _find_order(db, order_no)
    if not found:
        raise HTTPException(status_code=404, detail="订单不存在")
    kind, order = found
    try:
        mall.apply_refund(db, order, reason=body.reason or "管理员退款", force=force)
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _order_out(db, kind, order)
