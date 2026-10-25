"""Web Push 投递服务。

边界与约定：
- VAPID 密钥只从环境变量读取（VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY /
  VAPID_SUBJECT），密钥文件 backend/.env 已被 .gitignore 排除。
- 推送内容只来自已经生成的站内通知，不额外读取病历、用药或医院数据。
- 推送地址（endpoint）本身可作为投递凭据，错误日志只记录状态码。
- 设备返回 404/410 表示订阅失效，直接删除，避免反复无效投递。
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Notification, PushDelivery, PushSubscription, User

logger = logging.getLogger("app.push")

PUSH_TTL_SECONDS = 24 * 60 * 60
PUSH_TIMEOUT_SECONDS = 10
PENDING_WINDOW = timedelta(hours=48)
MAX_PENDING_PER_SCAN = 50
MAX_BODY_CHARS = 280
ICON_URL = "/icon-192.png"

# 只接受主流浏览器推送服务的地址，避免被用来请求任意 HTTPS 主机。
# 自建推送服务可通过 PUSH_ALLOWED_HOSTS 追加（逗号分隔）。
PUSH_HOSTS = {
    "fcm.googleapis.com",
    "android.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "notify.windows.com",
    "web.push.apple.com",
}


def _allowed_push_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    extra = {
        item.strip().lower()
        for item in (os.getenv("PUSH_ALLOWED_HOSTS") or "").split(",")
        if item.strip()
    }
    for suffix in PUSH_HOSTS | extra:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


class PushNotConfigured(Exception):
    """服务端未配置 VAPID 密钥。"""


class NoPushSubscription(Exception):
    """当前用户还没有可用的订阅设备。"""


def now() -> datetime:
    return datetime.utcnow()


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    value = (text or "").strip()
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass(frozen=True)
class VapidConfig:
    enabled: bool
    public_key: str
    # base64url 原始私钥；py_vapid 的 from_string 按 RAW/DER 自动识别
    private_key: str
    subject: str
    reason: str


def _disabled(reason: str) -> VapidConfig:
    return VapidConfig(False, "", "", "", reason)


@lru_cache(maxsize=1)
def vapid_config() -> VapidConfig:
    public_key = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    private_key = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    subject = (os.getenv("VAPID_SUBJECT") or "").strip() or "mailto:admin@xiaoyi.local"

    if not public_key or not private_key:
        return _disabled(
            "未配置 VAPID 密钥，手机通知暂不可用；"
            "运行 backend/scripts/generate_vapid_keys.py 生成后重启后端。"
        )

    try:
        raw_private = b64url_decode(private_key)
        if len(raw_private) != 32:
            raise ValueError("private key length")
        key = ec.derive_private_key(
            int.from_bytes(raw_private, "big"), ec.SECP256R1()
        )
        expected_public = b64url_encode(
            key.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        if expected_public != public_key:
            raise ValueError("vapid key mismatch")
    except Exception:
        logger.warning("VAPID 密钥格式无效，手机推送已关闭")
        return _disabled("VAPID 密钥格式无效，请重新生成后重启后端。")

    return VapidConfig(True, public_key, private_key, subject, "")


def public_config() -> dict:
    config = vapid_config()
    return {
        "enabled": config.enabled,
        "public_key": config.public_key if config.enabled else "",
        "subject": config.subject,
        "reason": config.reason,
    }


def _validate_subscription(endpoint: str, p256dh: str, auth: str) -> tuple[str, str, str]:
    endpoint = (endpoint or "").strip()
    p256dh = (p256dh or "").strip()
    auth = (auth or "").strip()
    parts = urlsplit(endpoint)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("不支持的推送地址")
    if not _allowed_push_host(parts.hostname):
        raise ValueError("不支持的推送服务")
    if len(endpoint) > 500:
        raise ValueError("推送地址过长")
    if not 20 <= len(p256dh) <= 200:
        raise ValueError("设备公钥格式不正确")
    if not 8 <= len(auth) <= 100:
        raise ValueError("设备授权信息格式不正确")
    try:
        if len(b64url_decode(p256dh)) != 65:
            raise ValueError
        if len(b64url_decode(auth)) != 16:
            raise ValueError
    except Exception as exc:
        raise ValueError("设备订阅密钥格式不正确") from exc
    return endpoint, p256dh, auth


def save_subscription(
    db: Session,
    user: User,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
) -> PushSubscription:
    endpoint, p256dh, auth = _validate_subscription(endpoint, p256dh, auth)
    current = now()
    row = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == endpoint)
        .first()
    )
    if row:
        # 同一浏览器换了账号登录时，订阅归当前用户
        row.user_id = user.id
        row.p256dh = p256dh
        row.auth = auth
        row.user_agent = (user_agent or "")[:300]
        row.enabled = True
        row.failure_count = 0
        row.last_error = ""
        row.updated_at = current
    else:
        row = PushSubscription(
            user_id=user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=(user_agent or "")[:300],
            enabled=True,
            created_at=current,
            updated_at=current,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_subscription(db: Session, user: User, endpoint: str) -> bool:
    row = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == (endpoint or "").strip(),
        )
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def status_for_user(db: Session, user: User) -> dict:
    config = vapid_config()
    subscriptions = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user.id,
            PushSubscription.enabled.is_(True),
        )
        .all()
    )
    last_success = max(
        (row.last_success_at for row in subscriptions if row.last_success_at),
        default=None,
    )
    return {
        "enabled": config.enabled,
        "reason": config.reason,
        "subscriptions": len(subscriptions),
        "last_success_at": last_success,
    }


def click_url(item: Notification) -> str:
    """通知点击后打开的前端页面；只允许应用内路径。"""
    external = (item.external_url or "").strip()
    if external.startswith("/") and not external.startswith("//"):
        return external
    if item.course_id:
        return f"/courses?id={item.course_id}"
    if item.reminder_id:
        return "/reminders"
    return "/notifications"


def _payload(item: Notification) -> str:
    body = (item.body or "").replace("\x00", "").strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "…"
    return json.dumps(
        {
            "title": item.title,
            "body": body,
            "url": click_url(item),
            "tag": f"xiaoyi-notification-{item.id}",
            "notification_id": item.id,
            "icon": ICON_URL,
        },
        ensure_ascii=False,
    )


def _send(
    subscription: PushSubscription, payload: str, config: VapidConfig
) -> tuple[bool, int | None, str]:
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload,
            vapid_private_key=config.private_key,
            vapid_claims={"sub": config.subject},
            ttl=PUSH_TTL_SECONDS,
            timeout=PUSH_TIMEOUT_SECONDS,
        )
        return True, None, ""
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        message = f"HTTP {status}" if status else "推送服务不可达"
        return False, status, message
    except Exception as exc:  # 网络、证书等异常不向外暴露细节
        logger.warning("推送投递异常：%s", type(exc).__name__)
        return False, None, "网络异常"


def _apply_result(
    subscription: PushSubscription,
    ok: bool,
    status: int | None,
    message: str,
    current: datetime,
) -> None:
    if ok:
        subscription.failure_count = 0
        subscription.last_error = ""
        subscription.last_success_at = current
    else:
        subscription.failure_count = (subscription.failure_count or 0) + 1
        subscription.last_error = message[:300]


def send_test(db: Session, user: User) -> dict:
    config = vapid_config()
    if not config.enabled:
        raise PushNotConfigured(config.reason)

    subscriptions = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user.id,
            PushSubscription.enabled.is_(True),
        )
        .all()
    )
    if not subscriptions:
        raise NoPushSubscription("当前设备还没有开启通知，请先允许通知权限")

    payload = json.dumps(
        {
            "title": "小医通知已开启",
            "body": "这是一条测试通知，点击可回到小医消息页。",
            "url": "/notifications",
            "tag": "xiaoyi-test",
            "icon": ICON_URL,
        },
        ensure_ascii=False,
    )
    current = now()
    sent = failed = 0
    last_error = ""
    for subscription in subscriptions:
        ok, status, message = _send(subscription, payload, config)
        _apply_result(subscription, ok, status, message, current)
        if ok:
            sent += 1
        else:
            failed += 1
            last_error = message
            if status in (404, 410):
                db.delete(subscription)
    db.commit()
    return {
        "sent": sent,
        "failed": failed,
        "total": len(subscriptions),
        "detail": last_error,
    }


def _deliver_one(
    db: Session, item: Notification, config: VapidConfig, current: datetime
) -> bool:
    subscriptions = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == item.user_id,
            PushSubscription.enabled.is_(True),
            # 只推给订阅早于通知的设备：刚开启通知时不会补推历史消息
            PushSubscription.created_at <= item.created_at + timedelta(seconds=1),
        )
        .all()
    )

    if not subscriptions:
        db.add(
            PushDelivery(
                notification_id=item.id,
                user_id=item.user_id,
                status="skipped",
                detail="无可用订阅设备",
                created_at=current,
            )
        )
        return False

    payload = _payload(item)
    sent = failed = 0
    last_error = ""
    for subscription in subscriptions:
        ok, status, message = _send(subscription, payload, config)
        _apply_result(subscription, ok, status, message, current)
        if ok:
            sent += 1
        else:
            failed += 1
            last_error = message
            if status in (404, 410):
                db.delete(subscription)

    detail = f"成功 {sent} 台，失败 {failed} 台"
    if last_error:
        detail = f"{detail}；{last_error}"
    db.add(
        PushDelivery(
            notification_id=item.id,
            user_id=item.user_id,
            status="sent" if sent else "failed",
            detail=detail[:300],
            created_at=current,
        )
    )
    return sent > 0


def deliver_pending(db: Session, limit: int = MAX_PENDING_PER_SCAN) -> int:
    """把最近生成、尚未投递的站内通知推送到用户设备。

    由提醒扫描器在提交事务后调用；单条失败不影响其他通知。
    """
    config = vapid_config()
    current = now()
    cutoff = current - PENDING_WINDOW
    items = (
        db.query(Notification)
        .outerjoin(PushDelivery, PushDelivery.notification_id == Notification.id)
        .filter(
            PushDelivery.id.is_(None),
            Notification.created_at >= cutoff,
        )
        .order_by(Notification.id.asc())
        .limit(limit)
        .all()
    )
    if not items:
        return 0

    delivered = 0
    for item in items:
        if not config.enabled:
            db.add(
                PushDelivery(
                    notification_id=item.id,
                    user_id=item.user_id,
                    status="skipped",
                    detail="推送未配置",
                    created_at=current,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
            continue
        try:
            if _deliver_one(db, item, config, current):
                delivered += 1
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception:
            db.rollback()
            logger.exception("通知 %s 推送失败", item.id)
    return delivered
