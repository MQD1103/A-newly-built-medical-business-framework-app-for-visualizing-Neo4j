# -*- coding: utf-8 -*-
"""给 COPD 课程补齐「用途分类」与「适用人群」，供商城目录侧栏筛选。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import Course
from app.schema_migrate import ensure_schema

# 课程 ID -> (用途分类, 适用人群)
CATEGORIES = {
    1: ("入门与自测", "新确诊患者"),
    2: ("康复与运动", "新确诊患者"),
    3: ("用药与氧疗", "长期管理患者"),
    4: ("长期管理与照护", "中重度进阶"),
    5: ("用药与氧疗", "中重度进阶"),
    6: ("入门与自测", "全部人群"),
    7: ("系统整包", "全部人群"),
    8: ("预防与防护", "全部人群"),
    9: ("营养与饮食", "长期管理患者"),
    10: ("预防与防护", "全部人群"),
    11: ("营养与饮食", "全部人群"),
    12: ("康复与运动", "长期管理患者"),
    13: ("预防与防护", "全部人群"),
    14: ("长期管理与照护", "长期管理患者"),
    15: ("入门与自测", "新确诊患者"),
    16: ("长期管理与照护", "中重度进阶"),
    17: ("长期管理与照护", "家属照护者"),
    18: ("长期管理与照护", "家属照护者"),
    19: ("用药与氧疗", "中重度进阶"),
    20: ("预防与防护", "长期管理患者"),
    21: ("预防与防护", "家属照护者"),
    22: ("预防与防护", "全部人群"),
    23: ("康复与运动", "中重度进阶"),
    24: ("用药与氧疗", "长期管理患者"),
    25: ("长期管理与照护", "家属照护者"),
    26: ("康复与运动", "长期管理患者"),
    27: ("入门与自测", "全部人群"),
    28: ("入门与自测", "长期管理患者"),
    29: ("长期管理与照护", "长期管理患者"),
}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        changed = 0
        for c in db.query(Course).order_by(Course.id).all():
            pair = CATEGORIES.get(c.id)
            if not pair:
                continue
            if (c.category or "") != pair[0] or (c.audience or "") != pair[1]:
                c.category, c.audience = pair
                changed += 1
        db.commit()
        for c in db.query(Course).order_by(Course.id).all():
            print(f"{c.id}\t{c.category or '-'}\t{c.audience or '-'}\t{c.name}")
        print(f"更新 {changed} 门")
    finally:
        db.close()


if __name__ == "__main__":
    main()
