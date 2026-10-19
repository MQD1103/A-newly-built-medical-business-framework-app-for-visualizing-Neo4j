"""进程内滑动窗口限流。

用于登录等敏感接口的基础防护。单机演示足够；多实例部署时应换成 Redis
等共享存储，否则每个实例各自计数。
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import defaultdict


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = max(1, int(limit))
        self.window = max(1, int(window_seconds))
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str, current: float) -> None:
        cutoff = current - self.window
        events = self._events.get(key)
        if not events:
            return
        self._events[key] = [ts for ts in events if ts > cutoff]
        if not self._events[key]:
            self._events.pop(key, None)

    def retry_after(self, key: str) -> int:
        """还可以尝试返回 0；超限返回建议等待秒数。"""
        current = time.monotonic()
        with self._lock:
            self._prune(key, current)
            events = self._events.get(key) or []
            if len(events) < self.limit:
                return 0
            wait = self.window - (current - events[0])
            return max(1, math.ceil(wait))

    def hit(self, key: str) -> None:
        current = time.monotonic()
        with self._lock:
            self._prune(key, current)
            self._events[key].append(current)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


LOGIN_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "10") or "10")
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "300") or "300")
LOGIN_IP_LIMIT = int(os.getenv("LOGIN_IP_LIMIT", "30") or "30")

login_limiter = SlidingWindowLimiter(LOGIN_LIMIT, LOGIN_WINDOW_SECONDS)
login_ip_limiter = SlidingWindowLimiter(LOGIN_IP_LIMIT, LOGIN_WINDOW_SECONDS)
