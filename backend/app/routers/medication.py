"""用药打卡：长期用药计划 + 每日打卡 + 依从性回顾。

设计要点：
- 「计划」是长期安排（药名、每日次数、时间点），「打卡记录」是每天每次的结果。
- 当天槽位在查询今日清单时自动补齐，用户不必先建记录再打卡。
- 同一计划同一天同一班次重复打卡是更新，不产生重复记录。
- 应服次数按计划推算，不依赖是否打开过应用，避免漏算依从率。
- 只做自我记录，不给用药建议。
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import MedicationLog, MedicationPlan, User
from ..schemas import (
    MEDICATION_DISCLAIMER,
    MedicationAdherenceOut,
    MedicationCheckInIn,
    MedicationLogOut,
    MedicationPlanIn,
    MedicationPlanOut,
    MedicationPlanUpdate,
    MedicationSlotOut,
    MedicationTodayOut,
)

router = APIRouter(prefix="/api/medication", tags=["medication"])

VALID_STATUSES = ("pending", "taken", "skipped")
PLAN_STATUSES = ("active", "paused", "archived")


def parse_times(raw: str, frequency: int) -> list[str]:
    """解析 "08:00,20:00"；不足补空，多余截断到每日次数。"""
    slots: list[str] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if len(part) != 5 or part[2] != ":" or not part.replace(":", "").isdigit():
            raise HTTPException(status_code=400, detail=f"时间格式应为 HH:MM：{part}")
        hour, minute = int(part[:2]), int(part[3:])
        if hour > 23 or minute > 59:
            raise HTTPException(status_code=400, detail=f"时间超出范围：{part}")
        slots.append(part)
    slots = slots[:frequency]
    slots += [""] * (frequency - len(slots))
    return slots


def plan_active_on(plan: MedicationPlan, day: date) -> bool:
    """该计划在指定日期是否应服药（只统计进行中的计划）。"""
    if (plan.status or "active") != "active":
        return False
    if day < plan.start_date:
        return False
    return plan.end_date is None or day <= plan.end_date


def ensure_day_slots(db: Session, plan: MedicationPlan, day: date) -> list[MedicationLog]:
    """补齐某天的打卡槽位；已有记录不动，返回当天的全部槽位。"""
    times = parse_times(plan.times, plan.frequency)
    existing = {
        log.slot: log
        for log in db.query(MedicationLog)
        .filter(MedicationLog.plan_id == plan.id, MedicationLog.take_date == day)
        .all()
    }
    created = False
    for index in range(1, plan.frequency + 1):
        if index in existing:
            continue
        db.add(
            MedicationLog(
                plan_id=plan.id,
                user_id=plan.user_id,
                take_date=day,
                slot=index,
                scheduled_time=times[index - 1],
                status="pending",
            )
        )
        created = True
    if created:
        db.flush()
    return (
        db.query(MedicationLog)
        .filter(MedicationLog.plan_id == plan.id, MedicationLog.take_date == day)
        .order_by(MedicationLog.slot)
        .all()
    )


def get_plan(db: Session, plan_id: int, user: User) -> MedicationPlan:
    plan = db.get(MedicationPlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    return plan


@router.get("/plans", response_model=list[MedicationPlanOut])
def list_plans(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(MedicationPlan).filter(MedicationPlan.user_id == user.id)
    if not include_archived:
        q = q.filter(MedicationPlan.status != "archived")
    return q.order_by(MedicationPlan.status, MedicationPlan.id.desc()).all()


@router.post("/plans", response_model=MedicationPlanOut)
def create_plan(
    body: MedicationPlanIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start = body.start_date or date.today()
    if body.end_date and body.end_date < start:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    # 校验时间点格式，非法直接 400
    parse_times(body.times, body.frequency)

    plan = MedicationPlan(
        user_id=user.id,
        drug_name=body.drug_name.strip(),
        dosage=body.dosage.strip(),
        frequency=body.frequency,
        times=body.times.strip(),
        start_date=start,
        end_date=body.end_date,
        status="active",
        note=(body.note or "").strip(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/plans/{plan_id}", response_model=MedicationPlanOut)
def update_plan(
    plan_id: int,
    body: MedicationPlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan(db, plan_id, user)
    if body.status is not None and body.status not in PLAN_STATUSES:
        raise HTTPException(status_code=400, detail="计划状态不合法")

    frequency = body.frequency or plan.frequency
    if body.times is not None:
        parse_times(body.times, frequency)

    if body.drug_name is not None:
        plan.drug_name = body.drug_name.strip()
    if body.dosage is not None:
        plan.dosage = body.dosage.strip()
    if body.frequency is not None:
        plan.frequency = body.frequency
    if body.times is not None:
        plan.times = body.times.strip()
    if body.start_date is not None:
        plan.start_date = body.start_date
    if body.end_date is not None:
        plan.end_date = body.end_date
    if body.clear_end_date:
        plan.end_date = None
    if body.status is not None:
        plan.status = body.status
    if body.note is not None:
        plan.note = body.note.strip()

    if plan.end_date and plan.end_date < plan.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")

    # 次数变少时清掉多余槽位，避免历史记录里出现超出次数的打卡
    if plan.frequency and body.frequency is not None:
        db.query(MedicationLog).filter(
            MedicationLog.plan_id == plan.id,
            MedicationLog.slot > plan.frequency,
            MedicationLog.status == "pending",
        ).delete(synchronize_session=False)

    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan(db, plan_id, user)
    db.query(MedicationLog).filter(MedicationLog.plan_id == plan.id).delete(
        synchronize_session=False
    )
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.get("/today", response_model=MedicationTodayOut)
def today_slots(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """今日待打卡清单；当天槽位按需自动补齐。"""
    today = date.today()
    plans = (
        db.query(MedicationPlan)
        .filter(MedicationPlan.user_id == user.id, MedicationPlan.status == "active")
        .order_by(MedicationPlan.id)
        .all()
    )
    items: list[MedicationSlotOut] = []
    for plan in plans:
        if not plan_active_on(plan, today):
            continue
        for log in ensure_day_slots(db, plan, today):
            items.append(
                MedicationSlotOut(
                    log_id=log.id,
                    plan_id=plan.id,
                    drug_name=plan.drug_name,
                    dosage=plan.dosage or "",
                    take_date=log.take_date,
                    slot=log.slot,
                    scheduled_time=log.scheduled_time or "",
                    status=log.status or "pending",
                    checked_at=log.checked_at,
                    note=log.note or "",
                )
            )
    db.commit()

    taken = sum(1 for i in items if i.status == "taken")
    skipped = sum(1 for i in items if i.status == "skipped")
    return MedicationTodayOut(
        date=today,
        items=items,
        total=len(items),
        taken=taken,
        skipped=skipped,
        pending=len(items) - taken - skipped,
        disclaimer=MEDICATION_DISCLAIMER,
    )


@router.post("/checkin", response_model=MedicationSlotOut)
def check_in(
    body: MedicationCheckInIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """打卡；status=pending 表示撤销本次打卡。"""
    plan = get_plan(db, body.plan_id, user)
    status = (body.status or "taken").strip()
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="打卡状态不合法")

    take_date = body.take_date or date.today()
    if take_date > date.today():
        raise HTTPException(status_code=400, detail="不能给未来的日期打卡")
    if body.slot > plan.frequency:
        raise HTTPException(status_code=400, detail="班次超出该计划的每日次数")

    log = (
        db.query(MedicationLog)
        .filter(
            MedicationLog.plan_id == plan.id,
            MedicationLog.take_date == take_date,
            MedicationLog.slot == body.slot,
        )
        .first()
    )
    if log is None:
        times = parse_times(plan.times, plan.frequency)
        log = MedicationLog(
            plan_id=plan.id,
            user_id=user.id,
            take_date=take_date,
            slot=body.slot,
            scheduled_time=times[body.slot - 1],
            status="pending",
        )
        db.add(log)
        db.flush()

    log.status = status
    log.note = (body.note or "").strip()
    log.checked_at = None if status == "pending" else datetime.utcnow()
    log.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(log)

    return MedicationSlotOut(
        log_id=log.id,
        plan_id=plan.id,
        drug_name=plan.drug_name,
        dosage=plan.dosage or "",
        take_date=log.take_date,
        slot=log.slot,
        scheduled_time=log.scheduled_time or "",
        status=log.status,
        checked_at=log.checked_at,
        note=log.note or "",
    )


@router.get("/logs", response_model=list[MedicationLogOut])
def list_logs(
    days: int = Query(default=30, ge=1, le=365),
    plan_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    since = today - timedelta(days=days - 1)
    q = (
        db.query(MedicationLog)
        .filter(
            MedicationLog.user_id == user.id,
            MedicationLog.take_date >= since,
            MedicationLog.take_date <= today,
            MedicationLog.status != "pending",
        )
    )
    if plan_id:
        q = q.filter(MedicationLog.plan_id == plan_id)
    rows = q.order_by(MedicationLog.take_date.desc(), MedicationLog.slot).all()

    plans = {
        p.id: p
        for p in db.query(MedicationPlan).filter(MedicationPlan.user_id == user.id).all()
    }
    items: list[MedicationLogOut] = []
    for log in rows:
        plan = plans.get(log.plan_id)
        items.append(
            MedicationLogOut(
                id=log.id,
                plan_id=log.plan_id,
                drug_name=plan.drug_name if plan else "",
                dosage=plan.dosage if plan else "",
                take_date=log.take_date,
                slot=log.slot,
                scheduled_time=log.scheduled_time or "",
                status=log.status or "pending",
                checked_at=log.checked_at,
                note=log.note or "",
            )
        )
    return items


@router.get("/adherence", response_model=MedicationAdherenceOut)
def adherence(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """近 N 天依从率：应服次数按计划推算，与是否打开应用无关。"""
    today = date.today()
    since = today - timedelta(days=days - 1)
    plans = (
        db.query(MedicationPlan)
        .filter(MedicationPlan.user_id == user.id)
        .all()
    )

    logs = (
        db.query(MedicationLog)
        .filter(
            MedicationLog.user_id == user.id,
            MedicationLog.take_date >= since,
            MedicationLog.take_date <= today,
        )
        .all()
    )
    taken_by_day: dict[date, int] = {}
    skipped_by_day: dict[date, int] = {}
    for log in logs:
        bucket = taken_by_day if log.status == "taken" else skipped_by_day
        if log.status in ("taken", "skipped"):
            bucket[log.take_date] = bucket.get(log.take_date, 0) + 1

    scheduled = 0
    scheduled_by_day: dict[date, int] = {}
    for plan in plans:
        day = max(plan.start_date, since)
        last = min(plan.end_date or today, today)
        while day <= last:
            if plan_active_on(plan, day):
                scheduled += plan.frequency
                scheduled_by_day[day] = scheduled_by_day.get(day, 0) + plan.frequency
            day += timedelta(days=1)

    taken = sum(taken_by_day.values())
    skipped = sum(skipped_by_day.values())
    missed = max(0, scheduled - taken - skipped)
    rate = round(taken / scheduled * 100, 1) if scheduled else 0.0

    # 连续达标天数：当天应服次数全部完成才算达标，无计划的日期跳过
    streak = 0
    day = today
    while day >= since:
        need = scheduled_by_day.get(day, 0)
        if need == 0:
            day -= timedelta(days=1)
            continue
        if taken_by_day.get(day, 0) >= need:
            streak += 1
        else:
            break
        day -= timedelta(days=1)

    return MedicationAdherenceOut(
        days=days,
        from_date=since,
        to_date=today,
        scheduled=scheduled,
        taken=taken,
        skipped=skipped,
        missed=missed,
        rate=rate,
        streak_days=streak,
        plan_count=sum(1 for p in plans if (p.status or "active") == "active"),
        disclaimer=MEDICATION_DISCLAIMER,
    )
