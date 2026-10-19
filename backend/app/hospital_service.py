"""医院对接适配层。

把「合作医院开通、用户授权、只读资料拉取与缓存」集中在这里，业务路由不直接
拼医院地址。真实医院接口只通过环境变量配置：

- HOSPITAL_API_BASE_URL：医院接口根地址（不写入仓库）
- HOSPITAL_API_TOKEN：调用凭据（不写入仓库）
- HOSPITAL_API_TIMEOUT_SECONDS：单次请求超时，默认 8 秒

没有配置真实接口时，仅 mode=demo 的演示医院可用内置数据；mode=http 的医院
会返回可理解的“未配置”错误。日志只记录合作医院编码，不记录患者标识或病历内容。
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import HospitalAuthorization, HospitalPartner, HospitalRecord

logger = logging.getLogger("app.hospital")

RECORD_TYPES = ("advice", "condition", "record")
MODE_DEMO = "demo"
MODE_HTTP = "http"


class HospitalError(Exception):
    """可直接转换为接口错误的对接异常。"""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def now() -> datetime:
    return datetime.utcnow()


def mask_patient_ref(value: str) -> str:
    """列表接口只展示脱敏后的医院患者标识。"""
    value = (value or "").strip()
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def authorization_active(auth: HospitalAuthorization, current: datetime | None = None) -> bool:
    current = current or now()
    if (auth.status or "") != "active":
        return False
    return auth.expires_at is None or auth.expires_at > current


def authorization_status(auth: HospitalAuthorization, current: datetime | None = None) -> str:
    if (auth.status or "") == "revoked":
        return "revoked"
    return "active" if authorization_active(auth, current) else "expired"


def active_authorizations(
    db: Session, user_id: int, current: datetime | None = None
) -> list[HospitalAuthorization]:
    current = current or now()
    rows = (
        db.query(HospitalAuthorization)
        .filter(HospitalAuthorization.user_id == user_id)
        .all()
    )
    return [row for row in rows if authorization_active(row, current)]


def _demo_records(partner: HospitalPartner, current: datetime) -> list[dict]:
    """演示医院数据。只描述步骤/随访事项，不给诊断或药效结论。"""
    department = partner.department or "呼吸内科"
    return [
        {
            "external_id": "demo-advice-1",
            "record_type": "advice",
            "title": "用药与复查嘱托（演示）",
            "content": (
                "按医生医嘱规律用药，不自行停药或调整剂量。\n"
                "如出现气促明显加重、痰量增多或发热，请及时就医。\n"
                "建议 3 个月后复查肺功能。"
            ),
            "doctor_name": "演示医生",
            "department": department,
            "occurred_at": current - timedelta(days=2),
        },
        {
            "external_id": "demo-condition-1",
            "record_type": "condition",
            "title": "稳定期随访摘要（演示）",
            "content": (
                "近 4 周无明显急性加重，日常活动耐力基本稳定。\n"
                "本摘要为演示数据，仅用于功能联调，不作为诊疗依据。"
            ),
            "doctor_name": "演示医生",
            "department": department,
            "occurred_at": current - timedelta(days=10),
        },
        {
            "external_id": "demo-record-1",
            "record_type": "record",
            "title": "肺功能检查摘要（演示）",
            "content": (
                "检查项目：肺功能（演示）。\n"
                "结果请以医院正式报告和医生解读为准。\n"
                "本页只读，不提供修改病历或开药功能。"
            ),
            "doctor_name": "演示医生",
            "department": department,
            "occurred_at": current - timedelta(days=30),
        },
    ]


def _http_records(partner: HospitalPartner, patient_ref: str) -> list[dict]:
    base = os.getenv("HOSPITAL_API_BASE_URL", "").strip().rstrip("/")
    token = os.getenv("HOSPITAL_API_TOKEN", "").strip()
    if not base:
        raise HospitalError("医院接口未配置，请联系管理员", 503)
    try:
        timeout = float(os.getenv("HOSPITAL_API_TIMEOUT_SECONDS", "8") or "8")
    except ValueError:
        timeout = 8.0
    timeout = max(1.0, min(timeout, 30.0))

    url = f"{base}/patients/{urllib.parse.quote(patient_ref, safe='')}/records"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")

    payload = None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                raw = resp.read()
            payload = json.loads(raw.decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise HospitalError("医院接口授权失败，请联系医院", 502) from exc
            if exc.code == 404:
                raise HospitalError("医院未找到该患者的授权信息", 404) from exc
            if exc.code == 429:
                raise HospitalError("医院接口繁忙，请稍后重试", 503) from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise HospitalError("医院接口返回格式异常", 502) from exc
        if attempt == 0:
            time.sleep(0.5)

    if payload is None:
        logger.warning("医院接口调用失败 partner=%s error=%s", partner.code, type(last_error).__name__)
        raise HospitalError("医院接口暂不可用，请稍后重试", 502)

    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise HospitalError("医院接口返回格式异常", 502)
    return [item for item in items if isinstance(item, dict)]


def fetch_records(partner: HospitalPartner, patient_ref: str, current: datetime | None = None) -> list[dict]:
    current = current or now()
    mode = (partner.mode or MODE_DEMO).strip()
    if mode == MODE_DEMO:
        return _demo_records(partner, current)
    if mode == MODE_HTTP:
        return _http_records(partner, patient_ref)
    raise HospitalError("医院对接方式未配置", 500)


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def sync_authorization(
    db: Session, auth: HospitalAuthorization, current: datetime | None = None
) -> tuple[int, int, int]:
    """拉取并缓存授权医院的只读资料；只 flush，由路由统一 commit。"""
    current = current or now()
    if not authorization_active(auth, current):
        raise HospitalError("授权已失效，请重新授权", 403)
    partner = auth.partner
    if partner is None:
        raise HospitalError("合作医院不存在", 404)
    if (partner.status or "enabled") != "enabled":
        raise HospitalError("该医院尚未开通，暂时无法拉取资料", 400)

    items = fetch_records(partner, auth.patient_ref, current)
    existing = {
        row.external_id: row
        for row in db.query(HospitalRecord)
        .filter(
            HospitalRecord.user_id == auth.user_id,
            HospitalRecord.partner_id == partner.id,
        )
        .all()
    }

    added = 0
    updated = 0
    for item in items:
        external_id = str(item.get("external_id") or "").strip()[:120]
        title = str(item.get("title") or "").strip()[:200]
        if not external_id or not title:
            continue
        record_type = str(item.get("record_type") or "record").strip()
        if record_type not in RECORD_TYPES:
            record_type = "record"
        row = existing.get(external_id)
        if row is None:
            row = HospitalRecord(
                user_id=auth.user_id,
                partner_id=partner.id,
                external_id=external_id,
                record_type=record_type,
                title=title,
                content=str(item.get("content") or ""),
                doctor_name=str(item.get("doctor_name") or "")[:80],
                department=str(item.get("department") or "")[:80],
                occurred_at=_parse_datetime(item.get("occurred_at")),
                fetched_at=current,
                created_at=current,
            )
            db.add(row)
            existing[external_id] = row
            added += 1
        else:
            row.record_type = record_type
            row.title = title
            row.content = str(item.get("content") or "")
            row.doctor_name = str(item.get("doctor_name") or "")[:80]
            row.department = str(item.get("department") or "")[:80]
            row.occurred_at = _parse_datetime(item.get("occurred_at"))
            row.fetched_at = current
            updated += 1

    db.flush()
    return added, updated, added + updated
