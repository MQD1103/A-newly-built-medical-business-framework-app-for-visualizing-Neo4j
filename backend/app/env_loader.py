"""轻量 .env 加载器。

后端不依赖 python-dotenv：启动时读取 backend/.env，把尚未存在的键写入
进程环境变量。已显式设置的环境变量优先，不会被文件覆盖。

密钥（VAPID、医院 Token 等）只放 .env 或部署平台的环境变量，不进仓库。
"""

from __future__ import annotations

import os
from pathlib import Path


def env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path | None = None) -> None:
    target = path or env_file_path()
    try:
        text = target.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value
