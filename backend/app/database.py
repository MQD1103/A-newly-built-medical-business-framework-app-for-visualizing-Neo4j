import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 默认仍是本机 SQLite；测试/备份脚本可用 DATABASE_URL 指向临时库。
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./edu.db")

_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # 正式库（MySQL）长连接可能被服务端回收，取连接前先探活
    pool_pre_ping=not _is_sqlite,
    pool_recycle=0 if _is_sqlite else 3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
