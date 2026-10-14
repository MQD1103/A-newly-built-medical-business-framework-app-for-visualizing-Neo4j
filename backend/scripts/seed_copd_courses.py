# -*- coding: utf-8 -*-
"""写入 / 修复 COPD 售课示例（标价 2.99 元）。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import (
    Course,
    CourseMaterial,
    Enrollment,
    Grade,
    Reminder,
    ReminderPreference,
    ScheduleSlot,
    User,
)
from app.schema_migrate import ensure_schema

COPD_COURSES = [
    (
        "COPD 认识与早期筛查",
        "COPD 系列",
        "了解慢性阻塞性肺疾病的成因、症状与早期筛查要点。",
    ),
    (
        "COPD 呼吸康复入门",
        "COPD 系列",
        "呼吸训练、活动耐力与居家康复的基础方法。",
    ),
    (
        "COPD 用药与吸入装置指导",
        "COPD 系列",
        "常用药物类别及吸入装置正确使用要点。",
    ),
    (
        "COPD 急性加重自我管理",
        "COPD 系列",
        "识别急性加重信号与就医、用药应对原则。",
    ),
    (
        "COPD 家庭氧疗与日常护理",
        "COPD 系列",
        "家庭氧疗注意事项与日常护理、防感染建议。",
    ),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        # 清空课程及关联后重建 COPD 售课
        rem_ids = [r.id for r in db.query(Reminder).filter(Reminder.course_id.isnot(None)).all()]
        if rem_ids:
            db.query(ReminderPreference).filter(
                ReminderPreference.reminder_id.in_(rem_ids)
            ).delete(synchronize_session=False)
            db.query(Reminder).filter(Reminder.id.in_(rem_ids)).delete(
                synchronize_session=False
            )
        db.query(ScheduleSlot).delete()
        db.query(CourseMaterial).delete()
        db.query(Grade).delete()
        db.query(Enrollment).delete()
        db.query(Course).delete()
        db.commit()

        admin = db.query(User).filter(User.role == "admin").first()
        tid = admin.id if admin else None
        for name, sem, desc in COPD_COURSES:
            db.add(
                Course(
                    name=name,
                    semester=sem,
                    teacher_id=tid,
                    description=desc,
                    price=2.99,
                )
            )
        db.commit()
        out = ROOT / "scripts" / "_copd_seed_result.txt"
        lines = [
            f"{c.id}\t¥{c.price:.2f}\t{c.name}"
            for c in db.query(Course).order_by(Course.id).all()
        ]
        out.write_text("\n".join(lines), encoding="utf-8")
        print(out.read_text(encoding="utf-8"))
    finally:
        db.close()


if __name__ == "__main__":
    main()
