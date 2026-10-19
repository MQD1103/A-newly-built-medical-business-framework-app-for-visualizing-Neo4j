"""提醒调度与站内通知。

设计要点：
- 提醒是「规则」，通知是「触发记录 + 收件箱」。
- 同一用户、同一提醒、同一触发档位只会生成一条通知（数据库唯一约束）。
- 触发档位：提前 7 天、提前 1 天、到期当天/已到期。
- 完成状态按用户单独记录，一位学习者标记完成不影响其他人。
- 调度器默认每 60 秒扫描一次；REMINDER_SCAN_SECONDS=0 可关闭。
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    CourseBundleItem,
    Enrollment,
    Notification,
    Reminder,
    ReminderCompletion,
    ReminderPreference,
    User,
)

logger = logging.getLogger("app.notifications")

TRIGGER_7D = "7d"
TRIGGER_1D = "1d"
TRIGGER_DUE = "due"
SCAN_HORIZON = timedelta(days=7)


def now() -> datetime:
    return datetime.utcnow()


def trigger_key_for(due_at: datetime | None, current: datetime | None = None) -> str | None:
    """当前时间对应的触发档位；不在提醒窗口内返回 None。"""
    if due_at is None:
        return None
    current = current or now()
    if current < due_at - SCAN_HORIZON:
        return None
    if current < due_at - timedelta(days=1):
        return TRIGGER_7D
    if current < due_at:
        return TRIGGER_1D
    if current <= due_at + SCAN_HORIZON:
        return TRIGGER_DUE
    return None


def _active_enrollment_user_ids(
    db: Session, course_ids: list[int], current: datetime
) -> set[int]:
    if not course_ids:
        return set()
    rows = (
        db.query(Enrollment.student_id)
        .filter(
            Enrollment.course_id.in_(course_ids),
            (Enrollment.expires_at.is_(None)) | (Enrollment.expires_at > current),
        )
        .all()
    )
    return {int(row[0]) for row in rows}


def reminder_recipient_ids(db: Session, reminder: Reminder, current: datetime) -> set[int]:
    """提醒应该触达哪些用户。"""
    if reminder.target_user_id:
        target = db.get(User, reminder.target_user_id)
        return {target.id} if target else set()

    if reminder.course_id:
        ids: set[int] = set()
        course = reminder.course
        if course and course.teacher_id:
            ids.add(int(course.teacher_id))
        ids |= _active_enrollment_user_ids(db, [reminder.course_id], current)
        # 整包购买者也能收到包内单课的提醒
        bundle_ids = [
            int(row[0])
            for row in db.query(CourseBundleItem.bundle_id)
            .filter(CourseBundleItem.course_id == reminder.course_id)
            .all()
        ]
        ids |= _active_enrollment_user_ids(db, bundle_ids, current)
        return ids

    if (reminder.source or "manager") == "user" or reminder.creator_id:
        return {int(reminder.creator_id)}

    return {int(row[0]) for row in db.query(User.id).all()}


def _disabled_user_ids(
    db: Session, reminder: Reminder, user_ids: set[int]
) -> set[int]:
    if not user_ids:
        return set()
    if (reminder.source or "manager") not in ("manager", "system"):
        return set()
    rows = (
        db.query(ReminderPreference.user_id)
        .filter(
            ReminderPreference.reminder_id == reminder.id,
            ReminderPreference.user_id.in_(user_ids),
            ReminderPreference.enabled.is_(False),
        )
        .all()
    )
    return {int(row[0]) for row in rows}


def _completed_user_ids(
    db: Session, reminder: Reminder, user_ids: set[int]
) -> set[int]:
    if not user_ids:
        return set()
    rows = (
        db.query(ReminderCompletion.user_id)
        .filter(
            ReminderCompletion.reminder_id == reminder.id,
            ReminderCompletion.user_id.in_(user_ids),
        )
        .all()
    )
    return {int(row[0]) for row in rows}


def _notification_body(reminder: Reminder, trigger_key: str, current: datetime) -> str:
    content = (reminder.content or "").strip()
    if trigger_key == TRIGGER_7D:
        prefix = "还有 7 天到期"
    elif trigger_key == TRIGGER_1D:
        prefix = "明天到期"
    elif reminder.due_at and current > reminder.due_at + timedelta(hours=1):
        prefix = "已到期"
    else:
        prefix = "今天到期"
    return f"{prefix}：{content}" if content else prefix


def sync_reminder_notifications(
    db: Session, reminder: Reminder, current: datetime | None = None
) -> int:
    """为单条提醒补齐通知；只 flush，不 commit，由调用方决定事务。"""
    current = current or now()
    key = trigger_key_for(reminder.due_at, current)
    if key is None:
        return 0

    recipients = reminder_recipient_ids(db, reminder, current)
    if not recipients:
        return 0
    recipients -= _disabled_user_ids(db, reminder, recipients)
    recipients -= _completed_user_ids(db, reminder, recipients)
    if not recipients:
        return 0

    existing = {
        int(row[0])
        for row in db.query(Notification.user_id)
        .filter(
            Notification.reminder_id == reminder.id,
            Notification.trigger_key == key,
        )
        .all()
    }
    missing = sorted(recipients - existing)
    if not missing:
        return 0

    body = _notification_body(reminder, key, current)
    for user_id in missing:
        db.add(
            Notification(
                user_id=user_id,
                reminder_id=reminder.id,
                course_id=reminder.course_id,
                trigger_key=key,
                title=reminder.title,
                body=body,
                external_url=reminder.external_url or "",
                due_at=reminder.due_at,
                created_at=current,
            )
        )
    return len(missing)


def sync_due_notifications(db: Session, current: datetime | None = None) -> int:
    """扫描未来 7 天至过期 7 天内的提醒，补齐通知。"""
    current = current or now()
    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.due_at >= current - SCAN_HORIZON,
            Reminder.due_at <= current + SCAN_HORIZON,
        )
        .all()
    )
    total = 0
    for reminder in reminders:
        total += sync_reminder_notifications(db, reminder, current)
    return total


def run_scan() -> int:
    """线程中执行的一次扫描（调度器与测试共用）。"""
    db = SessionLocal()
    try:
        count = sync_due_notifications(db)
        db.commit()
        return count
    except IntegrityError:
        # 多进程/多实例同时扫描时由唯一约束兜底
        db.rollback()
        return 0
    finally:
        db.close()


async def notification_worker() -> None:
    """FastAPI 生命周期内运行的轻量调度器。"""
    try:
        interval = int(os.getenv("REMINDER_SCAN_SECONDS", "60") or "60")
    except ValueError:
        interval = 60
    if interval <= 0:
        logger.info("提醒调度器已关闭（REMINDER_SCAN_SECONDS=%s）", interval)
        return
    logger.info("提醒调度器启动，扫描间隔 %s 秒", interval)
    while True:
        try:
            count = await asyncio.to_thread(run_scan)
            if count:
                logger.info("提醒扫描完成，新增站内通知 %s 条", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("提醒扫描失败")
        await asyncio.sleep(interval)
