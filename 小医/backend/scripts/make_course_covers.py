# -*- coding: utf-8 -*-
"""生成 COPD 课程封面 SVG，并写回 cover_url。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import Course
from app.schema_migrate import ensure_schema

UPLOAD = ROOT / "uploads" / "courses"

# 每套封面：文件名、渐变色、副标题
COVERS = [
    ("copd-screen.svg", "#1a6b8a", "#2bb3a0", "早期筛查"),
    ("copd-rehab.svg", "#2d6a4f", "#52b788", "呼吸康复"),
    ("copd-meds.svg", "#3d5a80", "#98c1d9", "用药指导"),
    ("copd-flare.svg", "#9b2226", "#ee9b00", "急性加重"),
    ("copd-oxygen.svg", "#1d3557", "#457b9d", "氧疗护理"),
]


def lung_svg(c1: str, c2: str, label: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="800" height="480" fill="url(#g)"/>
  <circle cx="640" cy="90" r="70" fill="rgba(255,255,255,0.12)"/>
  <circle cx="120" cy="400" r="90" fill="rgba(255,255,255,0.08)"/>
  <!-- stylized lungs -->
  <ellipse cx="340" cy="230" rx="70" ry="110" fill="rgba(255,255,255,0.22)"/>
  <ellipse cx="460" cy="230" rx="70" ry="110" fill="rgba(255,255,255,0.22)"/>
  <rect x="392" y="120" width="16" height="90" rx="8" fill="rgba(255,255,255,0.35)"/>
  <text x="40" y="70" fill="#fff" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="28" font-weight="700">小医 · COPD</text>
  <text x="40" y="420" fill="#fff" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="42" font-weight="700">{label}</text>
</svg>
"""


def main() -> None:
    UPLOAD.mkdir(parents=True, exist_ok=True)
    for fname, c1, c2, label in COVERS:
        (UPLOAD / fname).write_text(lung_svg(c1, c2, label), encoding="utf-8")

    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        courses = db.query(Course).order_by(Course.id).all()
        for i, c in enumerate(courses):
            fname = COVERS[i % len(COVERS)][0]
            c.cover_url = f"/uploads/courses/{fname}"
        db.commit()
        lines = [f"{c.id}\t{c.cover_url}\t{c.name}" for c in courses]
        (ROOT / "scripts" / "_covers.txt").write_text("\n".join(lines), encoding="utf-8")
    finally:
        db.close()


if __name__ == "__main__":
    main()
