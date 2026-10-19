import logging
import os
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger("app.auth")

# 生产环境必须设置 JWT_SECRET_KEY；未设置时使用仅限本机演示的默认值。
DEV_SECRET_KEY = "edu-framework-dev-secret-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip() or DEV_SECRET_KEY
if SECRET_KEY == DEV_SECRET_KEY:
    logger.warning("JWT_SECRET_KEY 未配置，正在使用演示密钥；上线前请务必更换")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)) or str(60 * 24 * 7)
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
