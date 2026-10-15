"""管理员代办：替其它用户开通/取消 课程与健康服务、下发/改删监督提醒、改资料。

与用户自助路径完全分开：
- 这里所有查询都按**目标用户**的 id 直接查 Enrollment / ServiceEntitlement，
  绝不使用 courses.enrolled_ids / service_products.owned_ids —— 那两个函数对
  admin 一律返回「全部」，拿来判断「别人有没有」必然出错。
- 替用户开通会写一条 ¥0 的订单（channel="admin"），用户能在购买记录里看到；
  取消只删开通关系，保留那条 ¥0 记录作为留痕。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..database import get_db
from ..deps import require_roles
from ..models import (
    Course,
    CoursePurchase,
    Enrollment,
    Reminder,
    ReminderPreference,
    ServiceEntitlement,
    ServiceProduct,
    ServicePurchase,
    User,
)
from ..schemas import (
    AdminCourseGrant,
    AdminOverviewOut,
    AdminReminderCreate,
    AdminReminderUpdate,
    AdminServiceGrant,
    AdminUserUpdate,
    UserOut,
)
from .courses import to_out as course_to_out
from .reminders import to_out as reminder_to_out
from .service_products import to_out as service_to_out

router = APIRouter(prefix="/api/admin", tags=["admin"])

# 代办开通的订单渠道标记，前端凭它显示「管理员开通」
GRANT_CHANNEL = "admin"


def get_target(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="管理员本就拥有全部功能，无需代办")
    return target


def target_enrolled_course_ids(db: Session, user_id: int) -> set[int]:
    return {
        e.course_id
        for e in db.query(Enrollment).filter(Enrollment.student_id == user_id).all()
    }


def target_owned_service_ids(db: Session, user_id: int) -> set[int]:
    return {
        e.service_id
        for e in db.query(ServiceEntitlement)
        .filter(ServiceEntitlement.user_id == user_id)
        .all()
    }


def build_overview(db: Session, target: User) -> AdminOverviewOut:
    enrolled = target_enrolled_course_ids(db, target.id)
    owned = target_owned_service_ids(db, target.id)

    courses = db.query(Course).order_by(Course.id).all()
    services = db.query(ServiceProduct).order_by(ServiceProduct.id).all()
    # 他名下的提醒：管理员点名下发的 + 自己建的 + 已开通课程下的
    conds = [
        Reminder.target_user_id == target.id,
        Reminder.creator_id == target.id,
    ]
    if enrolled:
        conds.append(Reminder.course_id.in_(enrolled))
    reminders = (
        db.query(Reminder)
        .filter(or_(*conds))
        .order_by(Reminder.due_at.asc())
        .all()
    )

    return AdminOverviewOut(
        user=UserOut.model_validate(target),
        courses=[course_to_out(c, enrolled) for c in courses],
        services=[service_to_out(s, owned) for s in services],
        reminders=[reminder_to_out(r, target, db) for r in reminders],
    )


@router.get("/users/{user_id}/overview", response_model=AdminOverviewOut)
def user_overview(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    target = get_target(db, user_id)
    return build_overview(db, target)


@router.post("/users/{user_id}/courses")
def grant_course(
    user_id: int,
    body: AdminCourseGrant,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    target = get_target(db, user_id)
    if target.role != "student":
        raise HTTPException(
            status_code=400,
            detail="教师的课程列表按其授课课程计算，无法用开通的方式添加",
        )
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    exists = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == target.id,
            Enrollment.course_id == course.id,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该用户已开通这门课程")

    db.add(Enrollment(student_id=target.id, course_id=course.id))
    db.add(
        CoursePurchase(
            user_id=target.id,
            course_id=course.id,
            amount=0.0,
            channel=GRANT_CHANNEL,
            status="paid",
        )
    )
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}/courses/{course_id}")
def revoke_course(
    user_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    target = get_target(db, user_id)
    rows = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == target.id,
            Enrollment.course_id == course_id,
        )
        .delete()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="该用户未开通这门课程")
    db.commit()
    # 订单记录保留：用户在购买记录里仍能看到「管理员开通」
    return {"ok": True}


@router.post("/users/{user_id}/services")
def grant_service(
    user_id: int,
    body: AdminServiceGrant,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    target = get_target(db, user_id)
    product = db.get(ServiceProduct, body.service_id)
    if not product:
        raise HTTPException(status_code=404, detail="服务不存在")
    exists = (
        db.query(ServiceEntitlement)
        .filter(
            ServiceEntitlement.user_id == target.id,
            ServiceEntitlement.service_id == product.id,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该用户已开通这项服务")

    db.add(ServiceEntitlement(user_id=target.id, service_id=product.id))
    db.add(
        ServicePurchase(
            user_id=target.id,
            service_id=product.id,
            amount=0.0,
            channel=GRANT_CHANNEL,
            status="paid",
        )
    )
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}/services/{service_id}")
def revoke_service(
    user_id: int,
    service_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    target = get_target(db, user_id)
    rows = (
        db.query(ServiceEntitlement)
        .filter(
            ServiceEntitlement.user_id == target.id,
            ServiceEntitlement.service_id == service_id,
        )
        .delete()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="该用户未开通这项服务")
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reminders")
def create_target_reminder(
    user_id: int,
    body: AdminReminderCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """管理员给指定用户下发一条监督提醒（source=manager，用户只可开关提醒）。"""
    target = get_target(db, user_id)
    reminder = Reminder(
        course_id=None,
        title=body.title.strip(),
        content=(body.content or "").strip(),
        due_at=body.due_at,
        external_url=(body.external_url or "").strip(),
        creator_id=admin.id,
        target_user_id=target.id,
        source="manager",
    )
    db.add(reminder)
    db.commit()
    return {"ok": True}


@router.patch("/reminders/{reminder_id}")
def update_any_reminder(
    reminder_id: int,
    body: AdminReminderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """管理员可直接改任意提醒（不经过 reminders.py 的 can_edit 规则）。"""
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if body.title is not None:
        reminder.title = body.title.strip()
    if body.content is not None:
        reminder.content = body.content.strip()
    if body.due_at is not None:
        reminder.due_at = body.due_at
    if body.external_url is not None:
        reminder.external_url = body.external_url.strip()
    db.commit()
    return {"ok": True}


@router.delete("/reminders/{reminder_id}")
def delete_any_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """管理员可删除任意提醒（含系统/管理者来源，普通用户端点做不到）。"""
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    db.query(ReminderPreference).filter(
        ReminderPreference.reminder_id == reminder_id
    ).delete()
    db.delete(reminder)
    db.commit()
    return {"ok": True}


@router.patch("/users/{user_id}")
def update_target_user(
    user_id: int,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """改他人姓名 / 重置密码（管理员操作，不需要对方旧密码）。"""
    target = get_target(db, user_id)
    if body.full_name is None and body.new_password is None:
        raise HTTPException(status_code=400, detail="没有需要修改的内容")
    if body.full_name is not None:
        target.full_name = body.full_name.strip()
    if body.new_password is not None:
        target.password_hash = hash_password(body.new_password)
    db.commit()
    db.refresh(target)
    return {"ok": True}
