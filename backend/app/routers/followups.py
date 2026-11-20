"""随访提醒：出院 / 门诊后的定期复查安排。

设计要点：
- 「计划」保存随访周期与下次到期日，「记录」保存每次实际随访的结果。
- 完成一次随访后按周期自动滚动出下一次到期日，并形成一条新的随访记录。
- 每条计划挂一条影子提醒（kind=checkup），复用既有「提醒 → 站内通知 →
  手机推送」链路，因此自动获得 7 天 / 1 天 / 到期三档提醒，不需要新的调度器。
- 暂停或结束计划会撤掉影子提醒，避免继续打扰；恢复时重新挂上。
- 只按用户填写的周期推算，不替代医生给出的复诊安排。
"""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    FollowUpPlan,
    FollowUpVisit,
    Notification,
    Reminder,
    ReminderCompletion,
    ReminderPreference,
    User,
)
from ..schemas import (
    FOLLOWUP_DISCLAIMER,
    FOLLOWUP_TYPES,
    FollowUpCompleteIn,
    FollowUpPlanIn,
    FollowUpPlanOut,
    FollowUpPlanUpdate,
    FollowUpSummaryOut,
    FollowUpVisitOut,
)

router = APIRouter(prefix="/api/followups", tags=["followups"])

PLAN_STATUSES = ("active", "paused", "closed")
DUE_SOON_DAYS = 7
# 随访到期当天上午提醒，与复查类提醒的习惯一致
DUE_TIME = time(9, 0)


def follow_type_label(follow_type: str) -> str:
    return FOLLOWUP_TYPES.get(follow_type or "other", follow_type or "其他")


def plan_state(plan: FollowUpPlan, today: date | None = None) -> tuple[str, int]:
    """返回 (状态, 距到期天数)；负数表示已逾期。"""
    today = today or date.today()
    if (plan.status or "active") == "closed":
        return "closed", (plan.next_due_date - today).days
    remaining = (plan.next_due_date - today).days
    if remaining < 0:
        return "overdue", remaining
    if remaining <= DUE_SOON_DAYS:
        return "due_soon", remaining
    return "upcoming", remaining


def to_visit_out(visit: FollowUpVisit) -> FollowUpVisitOut:
    return FollowUpVisitOut(
        id=visit.id,
        plan_id=visit.plan_id,
        visit_date=visit.visit_date,
        result=visit.result or "",
        next_due_date=visit.next_due_date,
        created_at=visit.created_at,
    )


def to_out(plan: FollowUpPlan, today: date | None = None) -> FollowUpPlanOut:
    state, remaining = plan_state(plan, today)
    return FollowUpPlanOut(
        id=plan.id,
        user_id=plan.user_id,
        title=plan.title,
        follow_type=plan.follow_type or "other",
        follow_type_label=follow_type_label(plan.follow_type),
        interval_days=plan.interval_days,
        last_visit_date=plan.last_visit_date,
        next_due_date=plan.next_due_date,
        hospital=plan.hospital or "",
        doctor=plan.doctor or "",
        status=plan.status or "active",
        note=plan.note or "",
        state=state,
        days_remaining=remaining,
        visit_count=len(plan.visits or []),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _reminder_content(plan: FollowUpPlan) -> str:
    parts = [f"{follow_type_label(plan.follow_type)}，每 {plan.interval_days} 天一次"]
    if plan.hospital:
        parts.append(plan.hospital)
    if plan.doctor:
        parts.append(f"{plan.doctor} 医生")
    parts.append("就诊请带上症状日记与用药记录")
    return " · ".join(parts)


def create_shadow_reminder(
    db: Session, plan: FollowUpPlan, user: User, parent_id: int | None = None
) -> Reminder:
    reminder = Reminder(
        title=f"随访提醒：{plan.title}",
        content=_reminder_content(plan),
        due_at=datetime.combine(plan.next_due_date, DUE_TIME),
        creator_id=user.id,
        target_user_id=user.id,
        source="user",
        kind="checkup",
        check_type=follow_type_label(plan.follow_type),
        repeat_rule="none",
        recurring_parent_id=parent_id,
    )
    db.add(reminder)
    db.flush()
    return reminder


def drop_shadow_reminder(db: Session, reminder_id: int | None) -> None:
    """撤掉影子提醒，并清理其通知与完成状态，避免继续推送。"""
    if not reminder_id:
        return
    for model in (Notification, ReminderCompletion, ReminderPreference):
        db.query(model).filter(model.reminder_id == reminder_id).delete(
            synchronize_session=False
        )
    reminder = db.get(Reminder, reminder_id)
    if reminder:
        db.delete(reminder)
    db.flush()


def get_plan(db: Session, plan_id: int, user: User) -> FollowUpPlan:
    plan = db.get(FollowUpPlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="随访计划不存在")
    return plan


@router.get("", response_model=list[FollowUpPlanOut])
def list_plans(
    include_closed: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(FollowUpPlan).filter(FollowUpPlan.user_id == user.id)
    if not include_closed:
        q = q.filter(FollowUpPlan.status != "closed")
    today = date.today()
    plans = q.order_by(FollowUpPlan.next_due_date).all()
    return [to_out(p, today) for p in plans]


@router.post("", response_model=FollowUpPlanOut)
def create_plan(
    body: FollowUpPlanIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.follow_type not in FOLLOWUP_TYPES:
        raise HTTPException(status_code=400, detail="随访类型不合法")
    next_due = body.next_due_date or (date.today() + timedelta(days=body.interval_days))
    if body.last_visit_date and body.last_visit_date > date.today():
        raise HTTPException(status_code=400, detail="上次随访日期不能是未来")

    plan = FollowUpPlan(
        user_id=user.id,
        title=body.title.strip(),
        follow_type=body.follow_type,
        interval_days=body.interval_days,
        last_visit_date=body.last_visit_date,
        next_due_date=next_due,
        hospital=body.hospital.strip(),
        doctor=body.doctor.strip(),
        status="active",
        note=(body.note or "").strip(),
    )
    db.add(plan)
    db.flush()

    plan.reminder_id = create_shadow_reminder(db, plan, user).id
    db.commit()
    db.refresh(plan)
    return to_out(plan)


@router.patch("/{plan_id}", response_model=FollowUpPlanOut)
def update_plan(
    plan_id: int,
    body: FollowUpPlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan(db, plan_id, user)
    if body.follow_type is not None and body.follow_type not in FOLLOWUP_TYPES:
        raise HTTPException(status_code=400, detail="随访类型不合法")
    if body.status is not None and body.status not in PLAN_STATUSES:
        raise HTTPException(status_code=400, detail="计划状态不合法")

    before_status = plan.status or "active"
    if body.title is not None:
        plan.title = body.title.strip()
    if body.follow_type is not None:
        plan.follow_type = body.follow_type
    if body.interval_days is not None:
        plan.interval_days = body.interval_days
    if body.next_due_date is not None:
        plan.next_due_date = body.next_due_date
    if body.hospital is not None:
        plan.hospital = body.hospital.strip()
    if body.doctor is not None:
        plan.doctor = body.doctor.strip()
    if body.note is not None:
        plan.note = body.note.strip()
    if body.status is not None:
        plan.status = body.status
    plan.updated_at = datetime.utcnow()

    after_status = plan.status or "active"
    if after_status != "active":
        # 暂停 / 结束：撤掉提醒，不再推送
        drop_shadow_reminder(db, plan.reminder_id)
        plan.reminder_id = None
    elif before_status != "active":
        # 恢复进行中：重新挂一条提醒
        plan.reminder_id = create_shadow_reminder(db, plan, user).id
    else:
        reminder = db.get(Reminder, plan.reminder_id) if plan.reminder_id else None
        if reminder:
            reminder.title = f"随访提醒：{plan.title}"
            reminder.content = _reminder_content(plan)
            reminder.due_at = datetime.combine(plan.next_due_date, DUE_TIME)
            reminder.check_type = follow_type_label(plan.follow_type)
        else:
            plan.reminder_id = create_shadow_reminder(db, plan, user).id

    db.commit()
    db.refresh(plan)
    return to_out(plan)


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan(db, plan_id, user)
    db.query(FollowUpVisit).filter(FollowUpVisit.plan_id == plan.id).delete(
        synchronize_session=False
    )
    drop_shadow_reminder(db, plan.reminder_id)
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.get("/summary", response_model=FollowUpSummaryOut)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    plans = (
        db.query(FollowUpPlan)
        .filter(FollowUpPlan.user_id == user.id)
        .order_by(FollowUpPlan.next_due_date)
        .all()
    )
    out = FollowUpSummaryOut(
        visit_count=db.query(FollowUpVisit)
        .filter(FollowUpVisit.user_id == user.id)
        .count()
    )
    for plan in plans:
        state, _ = plan_state(plan, today)
        setattr(out, state, getattr(out, state) + 1)
        out.active += 1 if (plan.status or "active") == "active" else 0

    upcoming = [
        p for p in plans
        if (p.status or "active") == "active" and p.next_due_date >= today
    ]
    if upcoming:
        nxt = upcoming[0]
        out.next_due_date = nxt.next_due_date
        out.next_title = nxt.title
    return out


@router.get("/{plan_id}/visits", response_model=list[FollowUpVisitOut])
def list_visits(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan(db, plan_id, user)
    rows = (
        db.query(FollowUpVisit)
        .filter(FollowUpVisit.plan_id == plan.id)
        .order_by(FollowUpVisit.visit_date.desc(), FollowUpVisit.id.desc())
        .all()
    )
    return [to_visit_out(v) for v in rows]


@router.post("/{plan_id}/complete", response_model=FollowUpPlanOut)
def complete_visit(
    plan_id: int,
    body: FollowUpCompleteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """完成一次随访：记录结果，并按周期排下一次。"""
    plan = get_plan(db, plan_id, user)
    visit_date = body.visit_date or date.today()
    if visit_date > date.today():
        raise HTTPException(status_code=400, detail="随访日期不能是未来")

    interval = body.interval_days or plan.interval_days
    next_due = visit_date + timedelta(days=interval)

    db.add(
        FollowUpVisit(
            plan_id=plan.id,
            user_id=user.id,
            visit_date=visit_date,
            result=(body.result or "").strip(),
            next_due_date=next_due,
        )
    )

    # 本轮提醒标记为完成，停止「已到期」推送；下一次另起一条提醒
    old_reminder_id = plan.reminder_id
    if old_reminder_id:
        exists = (
            db.query(ReminderCompletion)
            .filter(
                ReminderCompletion.reminder_id == old_reminder_id,
                ReminderCompletion.user_id == user.id,
            )
            .first()
        )
        if not exists:
            db.add(
                ReminderCompletion(
                    user_id=user.id,
                    reminder_id=old_reminder_id,
                    completed_at=datetime.utcnow(),
                )
            )

    plan.last_visit_date = visit_date
    plan.next_due_date = next_due
    plan.interval_days = interval
    plan.updated_at = datetime.utcnow()

    if (plan.status or "active") == "active":
        plan.reminder_id = create_shadow_reminder(
            db, plan, user, parent_id=old_reminder_id
        ).id

    db.commit()
    db.refresh(plan)
    return to_out(plan)


@router.get("/disclaimer")
def disclaimer():
    return {"disclaimer": FOLLOWUP_DISCLAIMER}
