"""为商城课时生成短演示视频（本地开发用）。

每个课时生成一个 10 秒、1280x720 的 H.264 MP4，写入
``backend/uploads/courses/demo/lesson-<id>.mp4``，并在数据库里为还没有
视频地址的课时补上 ``video_url``。不会覆盖管理员填写的真实视频地址。

视频文件默认不进仓库（见 .gitignore）；同事拉代码后执行本脚本即可重新生成。

依赖 ffmpeg：优先使用 PATH 中的 ffmpeg，其次使用可选依赖
``imageio-ffmpeg``：

    python -m pip install -r backend/requirements-dev.txt
    python backend/scripts/generate_demo_videos.py

常用参数：
    --force             重新生成已存在的演示视频
    --seconds 10        修改单个视频时长（默认 10 秒）
    --source clip.mp4   使用本地视频片源（需自行确认版权/授权），
                        统一裁成 1280x720、去掉音轨

示例（使用本地开源动画片源）：
    python backend/scripts/generate_demo_videos.py \
        --source backend/uploads/courses/demo/source-clip.mp4 --seconds 10 --force
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# 默认操作 backend/edu.db，与从哪个目录执行脚本无关
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///" + (BACKEND / "edu.db").as_posix()

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Lesson  # noqa: E402
from app.schema_migrate import ensure_schema  # noqa: E402
from app.seed import (  # noqa: E402
    DEMO_VIDEO_DIR,
    DEMO_VIDEO_SECONDS,
    seed_if_empty,
)

PALETTES = [
    ("0x0B3B3A", "0x14B8A6", "0xA7F3D0"),
    ("0x0B2E4F", "0x3B82F6", "0xBFDBFE"),
    ("0x1E1B4B", "0x6366F1", "0xC7D2FE"),
    ("0x14532D", "0x22C55E", "0xBBF7D0"),
    ("0x4C1D1A", "0xF97316", "0xFED7AA"),
]
FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    raise SystemExit(
        "未找到 ffmpeg。请安装 ffmpeg，或执行：\n"
        "  backend\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements-dev.txt"
    )


def find_font() -> Path | None:
    return next((p for p in FONT_CANDIDATES if p.is_file()), None)


def filter_graph(seconds: int, lesson_id: int, course_type: str, font: Path | None) -> str:
    background, accent, text_color = PALETTES[lesson_id % len(PALETTES)]
    parts = [
        f"drawbox=x=0:y=0:w=1280:h=720:color={background}:t=fill",
        f"drawbox=x='-300+t*160':y=140:w=360:h=360:color={accent}@0.28:t=fill",
        f"drawbox=x='1100-t*140':y=430:w=420:h=170:color={accent}@0.20:t=fill",
    ]
    if font is not None:
        font_path = str(font).replace("\\", "/").replace(":", "\\:")
        kind = "FREE INTRO" if course_type == "intro" else "COURSE DEMO"
        parts.extend(
            [
                "drawtext=fontfile='{}':text='COPD CARE':fontcolor=white:"
                "fontsize=64:x=(w-text_w)/2:y=250".format(font_path),
                "drawtext=fontfile='{}':text='{}  ·  LESSON {:02d}':"
                "fontcolor={}:fontsize=36:x=(w-text_w)/2:y=345".format(
                    font_path, kind, lesson_id, text_color
                ),
                "drawtext=fontfile='{}':text='{} SECOND SAMPLE':"
                "fontcolor=white@0.72:fontsize=24:x=(w-text_w)/2:y=410".format(
                    font_path, seconds
                ),
            ]
        )
    parts.extend(
        [
            f"fade=t=in:st=0:d=0.4",
            f"fade=t=out:st={max(seconds - 0.8, 0):.1f}:d=0.8",
        ]
    )
    return ",".join(parts)


def generate_poster(ffmpeg: str, video: Path) -> None:
    """抽取第 2 秒画面作为封面，避免播放器初始是黑屏。"""
    poster = video.with_suffix(".jpg")
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "2",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(poster),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0 or not poster.is_file():
        print(f"提示：lesson {video.stem} 封面生成失败，播放器将显示首帧。")


def generate_one(
    ffmpeg: str,
    font: Path | None,
    out: Path,
    lesson: Lesson,
    seconds: int,
    force: bool,
    source: Path | None = None,
) -> bool:
    if out.is_file() and not force:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    if source is not None:
        # 使用本地片源（需自行确认版权/授权），统一裁成 720p、去音轨
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-t",
            str(seconds),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ]
    else:
        course_type = lesson.course.course_type if lesson.course else "single"
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x0B3B3A:s=1280x720:r=30:d={seconds}",
            "-vf",
            filter_graph(seconds, int(lesson.id), course_type, font),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not out.is_file() or out.stat().st_size < 1000:
        raise SystemExit(
            f"生成失败：lesson {lesson.id}\n{result.stderr.strip()}"
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="重新生成已有视频")
    parser.add_argument(
        "--seconds", type=int, default=DEMO_VIDEO_SECONDS, help="单个视频时长（秒）"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="使用本地视频文件作为演示片源（需自行确认版权/授权）",
    )
    args = parser.parse_args()
    seconds = min(max(args.seconds, 3), 30)
    source = args.source.resolve() if args.source else None
    if source is not None and not source.is_file():
        raise SystemExit(f"片源不存在：{source}")

    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    created = 0
    attached = 0
    try:
        seed_if_empty(db)
        lessons = db.query(Lesson).order_by(Lesson.id).all()
        if not lessons:
            raise SystemExit("数据库中没有课时，请先启动后端完成演示数据初始化。")
        ffmpeg = find_ffmpeg()
        font = find_font()
        if font is None:
            print("未找到内置字体，视频将只显示色块（不影响播放）。")
        print(f"课时 {len(lessons)} 节，输出目录：{DEMO_VIDEO_DIR}")
        for lesson in lessons:
            out = DEMO_VIDEO_DIR / f"lesson-{lesson.id}.mp4"
            if generate_one(
                ffmpeg, font, out, lesson, seconds, args.force, source
            ):
                created += 1
            poster = out.with_suffix(".jpg")
            if args.force or not poster.is_file():
                generate_poster(ffmpeg, out)
            # 只补空地址；管理员填写的真实地址保持不动
            url = f"/uploads/courses/demo/{out.name}"
            if not (lesson.video_url or "").strip() or (
                args.force and lesson.video_url.startswith("/uploads/courses/demo/")
            ):
                lesson.video_url = url
                lesson.duration_seconds = seconds
                attached += 1
        db.commit()
    finally:
        db.close()

    total = len(list(DEMO_VIDEO_DIR.glob("lesson-*.mp4")))
    print(f"完成：新生成 {created} 个，挂载/更新课时 {attached} 个，目录内共 {total} 个视频。")


if __name__ == "__main__":
    main()
