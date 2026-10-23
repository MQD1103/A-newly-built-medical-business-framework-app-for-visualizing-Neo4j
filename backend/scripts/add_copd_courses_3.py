# -*- coding: utf-8 -*-
"""向课程列表追加三门 COPD 课程（八/九/十），并生成同风格封面 SVG。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import Course, User
from app.schema_migrate import ensure_schema

UPLOAD = ROOT / "uploads" / "courses"

# 名称、简介、封面文件名、渐变色1、渐变色2、封面副标题
NEW_COURSES = [
    (
        "COPD 戒烟与危险因素防控",
        "戒烟是延缓 COPD 进展最有效的单一干预措施。课程讲解烟草依赖的评估方法、渐进式戒烟计划与常见戒断症状的应对策略，并覆盖厨房通风、职业防护、雾霾天气出行等日常生活与环境危险因素的防控要点，帮助患者和家属从源头减少肺部损伤。",
        "copd-quit.svg", "#5f0f40", "#fb8b24", "戒烟防控",
    ),
    (
        "COPD 营养管理与体重维持",
        "营养不良和肌肉减少会直接削弱呼吸肌力量，加重气促与疲劳。课程介绍如何评估营养状况、计算每日能量与蛋白质需求，讲解少食多餐、食材选择与烹调技巧等实用方法，并提供适合呼吸功能不全者的抗阻训练配合建议，帮助您维持理想体重与肌肉量。",
        "copd-nutrition.svg", "#4a1942", "#e07a5f", "营养体重",
    ),
    (
        "COPD 疫苗接种与呼吸道感染预防",
        "呼吸道感染是 COPD 急性加重最常见的诱因。课程讲解流感疫苗、肺炎球菌疫苗、新冠疫苗等接种建议与时机，介绍洗手、佩戴口罩、室内通风等日常防护措施，以及感染发生后的早期识别与处理流程，帮助您把急性加重风险降到最低。",
        "copd-vaccine.svg", "#0b3954", "#087e8b", "疫苗防护",
    ),
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
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        tid = admin.id if admin else None
        style = {n[0]: (n[3], n[4], n[5]) for n in NEW_COURSES}
        added = []
        for name, desc, fname, c1, c2, label in NEW_COURSES:
            exists = db.query(Course).filter(Course.name == name).first()
            if exists:
                added.append((exists, fname))
                continue
            c = Course(
                name=name,
                semester="COPD 系列",
                teacher_id=tid,
                description=desc,
                price=2.99,
            )
            db.add(c)
            db.flush()
            added.append((c, fname))
        for c, fname in added:
            c1, c2, label = style[c.name]
            (UPLOAD / fname).write_text(lung_svg(c1, c2, label), encoding="utf-8")
            c.cover_url = f"/uploads/courses/{fname}"
        db.commit()
        for c in db.query(Course).order_by(Course.id).all():
            print(f"{c.id}\t{c.cover_url}\t{c.name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
