"""AI 用药动作检测的适配与结果摘要。

边界：
- 只接收用户主动拍摄的用药画面，处理后立即丢弃，**不保存原始影像**。
- 只保存「步骤是否完成 / 是否需要重做」摘要，不生成药效、诊断或调药结论。
- 检测服务异常时返回可理解提示，并引导用户重试或回看课程。

真实检测服务通过环境变量配置：
- AI_DETECTOR_URL：检测接口地址（不写入仓库）
- AI_DETECTOR_TOKEN：调用凭据（不写入仓库）
- AI_DETECTOR_TIMEOUT_SECONDS：超时，默认 10 秒
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import MedicationCheck

logger = logging.getLogger("app.ai")

DISCLAIMER = "结果仅表示步骤是否完成，不构成诊断或用药建议；如有不适请咨询医生。"
DEMO_MESSAGE = "演示模式：未接入真实识别服务，结果仅用于流程联调。"

IMAGE_SIGNATURES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda data: data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}


class DetectionError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def now() -> datetime:
    return datetime.utcnow()


def image_max_bytes() -> int:
    try:
        mb = float(os.getenv("AI_IMAGE_MAX_MB", "5") or "5")
    except ValueError:
        mb = 5.0
    mb = max(0.2, min(mb, 20.0))
    return int(mb * 1024 * 1024)


def retention_days() -> int:
    try:
        days = int(os.getenv("AI_RESULT_RETENTION_DAYS", "30") or "30")
    except ValueError:
        days = 30
    return max(1, min(days, 365))


def validate_image(data: bytes, content_type: str) -> None:
    content_type = (content_type or "").split(";")[0].strip().lower()
    check = IMAGE_SIGNATURES.get(content_type)
    if check is None:
        raise DetectionError("仅支持 JPG / PNG / WebP 图片", 400)
    if not data:
        raise DetectionError("图片为空，请重新拍摄", 400)
    if not check(data):
        raise DetectionError("图片格式与文件内容不一致，请重新拍摄", 400)


def _parse_result(payload) -> tuple[list[dict], bool, str]:
    if not isinstance(payload, dict):
        raise DetectionError("检测服务返回格式异常，请稍后重试")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise DetectionError("检测服务返回格式异常，请稍后重试")
    steps: list[dict] = []
    for item in raw_steps[:12]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:80]
        if not name:
            continue
        steps.append({"name": name, "done": bool(item.get("done"))})
    if not steps:
        raise DetectionError("检测服务没有返回可用步骤，请重新拍摄")
    message = str(payload.get("message") or "").strip()[:500]
    return steps, bool(payload.get("needs_retry")), message


def _http_detect(
    image: bytes,
    content_type: str,
    lesson_id: int | None,
    mode: str = "oral",
) -> tuple[list[dict], bool, str]:
    url = os.getenv("AI_DETECTOR_URL", "").strip()
    token = os.getenv("AI_DETECTOR_TOKEN", "").strip()
    if not url:
        raise DetectionError("检测服务未配置，请联系管理员", 503)
    try:
        timeout = float(os.getenv("AI_DETECTOR_TIMEOUT_SECONDS", "10") or "10")
    except ValueError:
        timeout = 10.0
    timeout = max(1.0, min(timeout, 60.0))

    headers = {
        "Content-Type": content_type,
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if lesson_id is not None:
        headers["X-Lesson-Id"] = str(lesson_id)
    headers["X-Medication-Mode"] = mode
    request = urllib.request.Request(url, data=image, headers=headers, method="POST")

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
                raise DetectionError("检测服务授权失败，请联系管理员", 502) from exc
            if exc.code == 429:
                raise DetectionError("检测服务繁忙，请稍后重试或回看课程", 503) from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise DetectionError("检测服务返回格式异常，请稍后重试", 502) from exc
        if attempt == 0:
            time.sleep(0.4)

    if payload is None:
        logger.warning("检测服务调用失败 error=%s", type(last_error).__name__)
        raise DetectionError("检测服务暂不可用，请稍后重试或回看课程", 502)
    return _parse_result(payload)


DEMO_STEPS = {
    "oral": [
        {"name": "核对药名与剂量", "done": True},
        {"name": "将药送入口中", "done": True},
        {"name": "完成吞咽动作", "done": False},
        {"name": "用药后留在画面内", "done": True},
    ],
    "inhale": [
        {"name": "摇匀吸入装置", "done": True},
        {"name": "先充分呼气", "done": True},
        {"name": "含紧吸嘴", "done": True},
        {"name": "深吸气", "done": False},
        {"name": "吸完后屏气", "done": False},
    ],
}


def detect(
    image: bytes,
    content_type: str,
    lesson_id: int | None = None,
    mode: str = "oral",
) -> tuple[list[dict], bool, str, str]:
    """返回 (步骤摘要, 是否需要重做, 提示, provider)。"""
    url = os.getenv("AI_DETECTOR_URL", "").strip()
    if not url:
        steps = [dict(item) for item in DEMO_STEPS.get(mode, DEMO_STEPS["oral"])]
        needs_retry = any(not item["done"] for item in steps)
        return steps, needs_retry, DEMO_MESSAGE, "demo"
    steps, needs_retry, message = _http_detect(image, content_type, lesson_id, mode)
    return steps, needs_retry, message, "http"


def prune_expired(db: Session, current: datetime | None = None) -> int:
    """按保留天数清理历史摘要；不保留任何影像。"""
    current = current or now()
    cutoff = current - timedelta(days=retention_days())
    deleted = (
        db.query(MedicationCheck)
        .filter(MedicationCheck.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    return int(deleted)


def steps_to_json(steps: list[dict]) -> str:
    return json.dumps(steps, ensure_ascii=False)


def steps_from_json(raw: str) -> list[dict]:
    try:
        value = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
