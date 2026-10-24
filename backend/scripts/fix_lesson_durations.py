"""把课时 duration_seconds 改成视频的真实时长（运行一次即可）。

    backend\\.venv\\Scripts\\python.exe backend\\scripts\\fix_lesson_durations.py

只处理本机 uploads 里已有视频文件、且配置了 video_url 的课时。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///" + (BACKEND / "edu.db").as_posix()

from app.database import SessionLocal  # noqa: E402
from app.models import Lesson  # noqa: E402


def video_duration_seconds(path: Path) -> int | None:
    from imageio_ffmpeg import get_ffmpeg_exe

    exe = get_ffmpeg_exe()
    import subprocess

    r = subprocess.run([exe, "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return None
    h, mi, s = m.groups()
    return round(int(h) * 3600 + int(mi) * 60 + float(s))


def main() -> None:
    db = SessionLocal()
    lessons = db.query(Lesson).filter(Lesson.video_url != "").all()
    changed = 0
    for lesson in lessons:
        m = re.match(r"/uploads/(.+)", lesson.video_url or "")
        if not m:
            continue
        f = BACKEND / "uploads" / m.group(1).replace("/", os.sep)
        if not f.exists():
            continue
        dur = video_duration_seconds(f)
        if dur is None:
            print(f"无法读取视频时长：{f.name}")
            continue
        if lesson.duration_seconds != dur:
            old = lesson.duration_seconds
            lesson.duration_seconds = dur
            changed += 1
            print(
                f"「{lesson.title}」{old // 60}:{old % 60:02d} -> {dur // 60}:{dur % 60:02d}"
            )
    db.commit()
    print(f"完成：更新 {changed} 个课时的显示时长。")


if __name__ == "__main__":
    main()
