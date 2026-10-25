"""生成 Web Push 所需的 VAPID 密钥并写入 backend/.env。

用法：
    python scripts/generate_vapid_keys.py           # 已存在则保留
    python scripts/generate_vapid_keys.py --force   # 覆盖并让旧订阅失效

公钥会打印出来，前端订阅时从后端接口获取，无需手工填写。
.env 已在 .gitignore 中，密钥不会进入仓库。
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
SUBJECT = "mailto:admin@xiaoyi.local"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return b64url(public_raw), b64url(private_raw)


def load_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def upsert(lines: list[str], key: str, value: str, force: bool) -> list[str]:
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.strip().startswith(prefix):
            if force:
                lines[index] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Web Push VAPID 密钥")
    parser.add_argument("--force", action="store_true", help="覆盖已有密钥")
    args = parser.parse_args()

    lines = load_lines()
    existing = "\n".join(lines)
    if (
        not args.force
        and "VAPID_PUBLIC_KEY=" in existing
        and "VAPID_PRIVATE_KEY=" in existing
    ):
        for line in lines:
            if line.startswith("VAPID_PUBLIC_KEY="):
                print(line.split("=", 1)[1])
                break
        print("已存在 VAPID 密钥，未修改。要重新生成请加 --force")
        return 0

    public_key, private_key = generate()
    if lines and lines[-1].strip():
        lines.append("")
    if not any(line.strip().startswith("# Web Push") for line in lines):
        lines.append("# Web Push（手机通知）：由 scripts/generate_vapid_keys.py 生成")
    lines = upsert(lines, "VAPID_PUBLIC_KEY", public_key, args.force)
    lines = upsert(lines, "VAPID_PRIVATE_KEY", private_key, args.force)
    lines = upsert(lines, "VAPID_SUBJECT", SUBJECT, args.force)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(public_key)
    print(f"已写入 {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
