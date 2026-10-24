"""为全部付费课课时配置视频地址（生成视频后运行一次即可）。

    backend\\.venv\\Scripts\\python.exe backend\\scripts\\attach_paid_videos.py

- 视频源目录：D:/医疗/paid/<序号>-<课程名>/<节序>-<标题>.mp4
- 目标：backend/uploads/courses/paid/lesson-<课时id>.mp4
- 按「课程名 + 课时在课程内的顺序」匹配数据库记录
- 若课时已有 video_url 则不覆盖（保护管理员手填的真实地址）
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

SRC_DIR = Path(r"D:\医疗\paid")

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///" + (BACKEND / "edu.db").as_posix()

from app.database import SessionLocal  # noqa: E402
from app.models import Course, Lesson  # noqa: E402


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>| ]', "", s)[:40]


def main() -> None:
    db = SessionLocal()
    courses = db.query(Course).filter(Course.course_type != "intro").all()
    if not courses:
        print("未找到付费课程，请先启动一次系统让种子数据建好。")
        return

    dest_dir = BACKEND / "uploads" / "courses" / "paid"
    dest_dir.mkdir(parents=True, exist_ok=True)

    changed = missing_file = missing_video = 0
    for course in courses:
        lessons = (
            db.query(Lesson)
            .filter(Lesson.course_id == course.id)
            .order_by(Lesson.sort_order, Lesson.id)
            .all()
        )
        # 找到本地视频目录：<序号>-<课程名>
        course_dirs = [d for d in SRC_DIR.iterdir() if d.is_dir() and d.name.endswith(safe_name(course.name))] if SRC_DIR.exists() else []
        for index, lesson in enumerate(lessons, start=1):
            if (lesson.video_url or "").strip():
                continue
            if not course_dirs:
                missing_video += 1
                continue
            src = course_dirs[0] / f"{index:02d}-{safe_name(lesson.title)}.mp4"
            if not src.exists():
                print(f"缺少视频文件：{course.name} 第{index}节「{lesson.title}」 -> {src.name}")
                missing_file += 1
                continue
            dest = dest_dir / f"lesson-{lesson.id}.mp4"
            shutil.copy2(src, dest)
            lesson.video_url = f"/uploads/courses/paid/lesson-{lesson.id}.mp4"
            changed += 1
            print(f"已配置「{course.name} · {lesson.title}」-> {lesson.video_url}")
    db.commit()
    print(f"完成：新配置 {changed} 个课时；缺视频文件 {missing_file} 个；无本地目录跳过 {missing_video} 个。")


if __name__ == "__main__":
    main()
