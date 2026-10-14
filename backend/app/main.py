from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routers import (
    auth,
    community,
    courses,
    grades,
    home,
    links,
    materials,
    notices,
    reminders,
    schedule,
    service_products,
    users,
)
from .schema_migrate import ensure_schema
from .seed import seed_if_empty

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
    yield


app = FastAPI(title="小医 · 医疗独特商业框架 API", version="0.1.0", lifespan=lifespan)

# 开发期允许本机与局域网前端访问（团队用 IP:5173 打开时也能调 API）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(notices.router)
app.include_router(courses.router)
app.include_router(service_products.router)
app.include_router(reminders.router)
app.include_router(schedule.router)
app.include_router(community.router)
app.include_router(materials.router)
app.include_router(grades.router)
app.include_router(links.router)
app.include_router(home.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
