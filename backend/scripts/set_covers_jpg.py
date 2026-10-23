# -*- coding: utf-8 -*-
"""把商城课程的封面换成 Desktop 提供的 10 张 JPG（按名称一一对应）。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import Course
from app.schema_migrate import ensure_schema

# 课程名 -> 封面文件
MAPPING = {
    "COPD 免费入门课：这门课能帮你做什么": "copd-intro.jpg",
    "COPD 系统课（整包）": "copd-system.jpg",
    "COPD 认识与早期筛查": "copd-screen.jpg",
    "COPD 呼吸康复入门": "copd-rehab.jpg",
    "COPD 用药与吸入装置指导": "copd-meds.jpg",
    "COPD 急性加重自我管理": "copd-flare.jpg",
    "COPD 家庭氧疗与日常护理": "copd-oxygen.jpg",
    "COPD 戒烟与危险因素防控": "copd-quit.jpg",
    "COPD 营养管理与体重维持": "copd-nutrition.jpg",
    "COPD 疫苗接种与呼吸道感染预防": "copd-vaccine.jpg",
}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    updated, missing = [], []
    try:
        for c in db.query(Course).all():
            fname = MAPPING.get(c.name.strip())
            if fname:
                path = ROOT / "uploads" / "courses" / fname
                if path.exists():
                    c.cover_url = f"/uploads/courses/{fname}"
                    updated.append(f"{c.id}\t{c.cover_url}\t{c.name}")
                else:
                    missing.append(f"{c.name} -> 缺文件 {fname}")
            else:
                missing.append(f"{c.name} -> 无映射")
        db.commit()
        print("已更新:")
        print("\n".join(updated))
        if missing:
            print("未处理:")
            print("\n".join(missing))
    finally:
        db.close()


if __name__ == "__main__":
    main()
