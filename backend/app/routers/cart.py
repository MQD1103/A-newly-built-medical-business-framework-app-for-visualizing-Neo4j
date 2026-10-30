"""商城购物车结算与优惠券 API（新增模块）。

购物车 CRUD 复用 mall.py 既有路由：
  GET/POST/DELETE /api/mall/cart[/...]
本模块只新增：
  POST /api/mall/checkout  结算（支持优惠券）
  GET  /api/mall/coupons        券列表（可领+我的）
  POST /api/mall/coupons/claim  领券
优惠券数据存于独立 coupons.db（SQLite），与主库完全隔离。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import mall_service as mall
from ..database import get_db
from ..deps import get_current_user
from ..models import User

router = APIRouter(prefix="/api/mall", tags=["mall-cart-coupon"])
# ---------- 购物车 CRUD（电商闭环：加车 → 结算 → 下单） ----------


def _cart_payload(db: Session, user: User) -> dict:
    items = mall.list_cart_items(db, user.id)
    rows = []
    for item in items:
        course = item.course
        rows.append(
            {
                "course_id": course.id,
                "course_name": course.name,
                "cover_url": course.cover_url or "",
                "price": mall.money(course.price),
            }
        )
    return {
        "items": rows,
        "count": len(rows),
        "total_amount": mall.money(sum(r["price"] for r in rows)),
    }


@router.get("/cart")
def get_cart(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _cart_payload(db, user)


@router.post("/cart/{course_id}")
def add_to_cart(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        mall.add_cart_item(db, user.id, course_id)
    except mall.MallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _cart_payload(db, user)


@router.delete("/cart/{course_id}")
def remove_from_cart(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mall.remove_cart_item(db, user.id, course_id)
    return _cart_payload(db, user)


@router.delete("/cart")
def clear_cart(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mall.clear_cart(db, user.id)
    return _cart_payload(db, user)

# ---------- 优惠券独立存储 ----------

COUPON_DB = Path(__file__).resolve().parent.parent.parent / "coupons.db"

SEED_COUPONS = [
    ("SAVE2", "满5减2券", 2.0, 5.0, 500),
    ("SAVE3", "满10减3券", 3.0, 10.0, 300),
    ("WELCOME5", "新人无门槛5元券", 5.0, 0.0, 100),
]


def _cdb() -> sqlite3.Connection:
    conn = sqlite3.connect(str(COUPON_DB))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            amount_off REAL NOT NULL,
            min_spend REAL NOT NULL DEFAULT 0,
            total_stock INTEGER NOT NULL DEFAULT 100,
            claimed_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS user_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unused',
            claimed_at TEXT NOT NULL,
            used_at TEXT,
            order_no TEXT DEFAULT '',
            UNIQUE(user_id, code)
        )"""
    )
    now = datetime.utcnow().isoformat()
    for code, title, off, minsp, stock in SEED_COUPONS:
        conn.execute(
            "INSERT OR IGNORE INTO coupons (code,title,amount_off,min_spend,total_stock,claimed_count,created_at) VALUES (?,?,?,?,?,0,?)",
            (code, title, off, minsp, stock, now),
        )
    conn.commit()
    return conn


class CheckoutIn(BaseModel):
    coupon_code: str | None = None


class ClaimIn(BaseModel):
    code: str


# ---------- 结算 ----------


@router.post("/checkout")
def checkout_cart(body: CheckoutIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = mall.list_cart_items(db, user.id)
    if not items:
        raise HTTPException(status_code=400, detail="购物车是空的")

    total = round(sum(mall.money(getattr(it.course, "price", 0.0) or 0.0) for it in items), 2)

    # 优惠券校验
    discount = 0.0
    coupon_code = (body.coupon_code or "").strip().upper()
    if coupon_code:
        conn = _cdb()
        try:
            row = conn.execute("SELECT * FROM coupons WHERE code = ?", (coupon_code,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="优惠券不存在")
            uc = conn.execute(
                "SELECT * FROM user_coupons WHERE user_id = ? AND code = ? AND status = 'unused'",
                (user.id, coupon_code),
            ).fetchone()
            if not uc:
                raise HTTPException(status_code=400, detail="你还没有这张券或已使用")
            if total < row["min_spend"]:
                raise HTTPException(status_code=400, detail=f"未满 ¥{row['min_spend']:.2f} 使用门槛")
            discount = min(row["amount_off"], total)
        finally:
            conn.close()

    # 逐课下单 + 按比例分摊折扣 + 立即模拟支付
    order_nos: list[str] = []
    try:
        remaining_discount = discount
        for idx, it in enumerate(items):
            order = mall.create_course_order(db, user, it.course_id, quantity=1, channel="mock")
            if discount > 0 and order.amount > 0 and total > 0:
                if idx == len(items) - 1:
                    cut = round(remaining_discount, 2)
                else:
                    cut = round(discount * (order.amount / total), 2)
                    remaining_discount -= cut
                cut = max(0.0, min(cut, order.amount))
                if cut > 0:
                    order.amount = round(order.amount - cut, 2)
                    order.discount_amount = round((order.discount_amount or 0.0) + cut, 2)
                    db.flush()
            mall.pay_course_order(db, order, channel="mock", transaction_id="")
            order_nos.append(order.order_no)
        mall.clear_cart(db, user.id)
        if coupon_code and discount > 0:
            conn = _cdb()
            try:
                conn.execute(
                    "UPDATE user_coupons SET status='used', used_at=?, order_no=? WHERE user_id=? AND code=? AND status='unused'",
                    (datetime.utcnow().isoformat(), ",".join(order_nos), user.id, coupon_code),
                )
                conn.commit()
            finally:
                conn.close()
        db.commit()
    except mall.MallError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return {
        "ok": True,
        "order_nos": order_nos,
        "total": total,
        "discount": round(discount, 2),
        "paid_amount": round(total - discount, 2),
        "count": len(order_nos),
    }


# ---------- 优惠券 ----------


@router.get("/coupons")
def list_coupons(user: User = Depends(get_current_user)):
    conn = _cdb()
    try:
        rows = conn.execute("SELECT * FROM coupons ORDER BY min_spend, amount_off").fetchall()
        mine_rows = conn.execute(
            "SELECT * FROM user_coupons WHERE user_id = ? ORDER BY claimed_at DESC", (user.id,)
        ).fetchall()
        mine_map = {r["code"]: r for r in mine_rows}
        available = []
        for r in rows:
            my = mine_map.get(r["code"])
            available.append(
                {
                    "code": r["code"],
                    "title": r["title"],
                    "amount_off": r["amount_off"],
                    "min_spend": r["min_spend"],
                    "left": max(0, r["total_stock"] - r["claimed_count"]),
                    "claimed": my is not None,
                    "status": my["status"] if my else None,
                }
            )
        mine = [
            {
                "code": r["code"],
                "status": r["status"],
                "claimed_at": r["claimed_at"],
                "used_at": r["used_at"],
            }
            for r in mine_rows
        ]
        return {"available": available, "mine": mine}
    finally:
        conn.close()


@router.post("/coupons/claim")
def claim_coupon(body: ClaimIn, user: User = Depends(get_current_user)):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="请输入券码")
    conn = _cdb()
    try:
        row = conn.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="优惠券不存在")
        if row["claimed_count"] >= row["total_stock"]:
            raise HTTPException(status_code=400, detail="已被抢光")
        try:
            conn.execute(
                "INSERT INTO user_coupons (user_id, code, status, claimed_at) VALUES (?,?,'unused',?)",
                (user.id, code, datetime.utcnow().isoformat()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="你已领取过这张券")
        conn.execute("UPDATE coupons SET claimed_count = claimed_count + 1 WHERE code = ?", (code,))
        conn.commit()
        return {"ok": True, "code": code, "title": row["title"]}
    finally:
        conn.close()