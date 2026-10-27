import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import notification_service
from .database import Base, SessionLocal, engine
from .observability import install_observability
from .routers import (
    admin,
    ai,
    auth,
    community,
    courses,
    friends,
    grades,
    health,
    home,
    hospital,
    links,
    mall,
    materials,
    notices,
    notifications,
    reminders,
    schedule,
    service_products,
    symptoms,
    users,
)
from .schema_migrate import ensure_schema
from .seed import seed_if_empty

logger = logging.getLogger("app.startup")

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"


@asynccontextmanager
async def lifespan(_: FastAPI):
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    (UPLOAD_ROOT / "avatars").mkdir(parents=True, exist_ok=True)
    (UPLOAD_ROOT / "community").mkdir(parents=True, exist_ok=True)
    (UPLOAD_ROOT / "courses").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()

    # 启动时先补一轮通知，之后由后台协程定时扫描
    try:
        notification_service.run_scan()
    except Exception:
        logger.exception("启动时通知扫描失败")

    notification_task = asyncio.create_task(notification_service.notification_worker())
    try:
        yield
    finally:
        notification_task.cancel()
        with suppress(asyncio.CancelledError):
            await notification_task


app = FastAPI(title="小医 · 医疗独特商业框架 API", version="0.1.0", lifespan=lifespan)

# 开发期允许本机与局域网前端访问（团队用 IP:5173 打开时也能调 API）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 最后注册，作为最外层中间件，记录所有请求（含 CORS 预检）
install_observability(app)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(notices.router)
app.include_router(notifications.router)
app.include_router(courses.router)
app.include_router(courses.lesson_quiz_router)
app.include_router(service_products.router)
app.include_router(mall.router)
app.include_router(reminders.router)
app.include_router(schedule.router)
app.include_router(community.router)
app.include_router(friends.router)
app.include_router(materials.router)
app.include_router(grades.router)
app.include_router(links.router)
app.include_router(hospital.router)
app.include_router(ai.router)
app.include_router(symptoms.router)
app.include_router(health.router)
app.include_router(home.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    """健康检查：同时确认数据库可用，方便排障时区分前后端问题。"""
    database_ok = True
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        database_ok = False
        logger.exception("健康检查：数据库不可用")
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "error",
        "time": datetime.utcnow().isoformat() + "Z",
    }
