"""为免费入门课课时配置视频地址（pull 本仓库后运行一次即可）。

    backend\\.venv\\Scripts\\python.exe backend\\scripts\\attach_intro_videos.py

若课时已有 video_url 则不覆盖（保护管理员手填的真实地址）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///" + (BACKEND / "edu.db").as_posix()

from app.database import SessionLocal  # noqa: E402
from app.models import Course, Lesson  # noqa: E402


def main() -> None:
    db = SessionLocal()
    intro = db.query(Course).filter(Course.course_type == "intro").first()
    if not intro:
        print("未找到免费入门课，请先启动一次系统让种子数据建好。")
        return
    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id == intro.id)
        .order_by(Lesson.sort_order, Lesson.id)
        .all()
    )
    changed = 0
    for index, lesson in enumerate(lessons, start=1):
        url = f"/uploads/courses/intro/lesson-{lesson.id}.mp4"
        if not (BACKEND / "uploads" / "courses" / "intro" / f"lesson-{lesson.id}.mp4").exists():
            print(f"跳过「{lesson.title}」：缺少视频文件 {url}")
            continue
        if (lesson.video_url or "").strip():
            print(f"跳过「{lesson.title}」：已有视频地址 {lesson.video_url}")
            continue
        lesson.video_url = url
        changed += 1
        print(f"已配置「{lesson.title}」-> {url}")
    db.commit()
    print(f"完成，共配置 {changed} 个课时。")


if __name__ == "__main__":
    main()
