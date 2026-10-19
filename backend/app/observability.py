"""基础可观测：统一日志格式、访问日志、请求 ID。

日志只记录方法、路径、状态码、耗时和客户端地址，不记录请求体，
避免把密码、患者信息或订单明细写进日志。
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request

logger = logging.getLogger("app.access")


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def install_observability(app: FastAPI) -> None:
    configure_logging()

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 - 记录后继续抛出
            elapsed = (time.perf_counter() - started) * 1000
            logger.exception(
                "request failed id=%s method=%s path=%s %.1fms client=%s error=%s",
                request_id,
                request.method,
                request.url.path,
                elapsed,
                request.client.host if request.client else "-",
                type(exc).__name__,
            )
            raise

        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        logger.log(
            level,
            "%s %s -> %s %.1fms id=%s client=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            request_id,
            request.client.host if request.client else "-",
        )
        return response
