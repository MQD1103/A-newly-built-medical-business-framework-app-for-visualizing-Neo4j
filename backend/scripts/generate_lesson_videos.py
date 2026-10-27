"""为课时生成「带教学要点」的短视频（本地开发 / 演示用）。

和 ``generate_demo_videos.py`` 的区别：
- 画面不是纯色块，而是按课时内容分屏：封面 → 本节要点 → 小结；
- 文字取自数据库里的课时标题与 summary，切题、可直接放进课程页播放；
- 输出到 ``backend/uploads/courses/lessons/lesson-<id>.mp4``，启动时由
  ``app/seed.py`` 优先挂载这个目录（没有时才回退到 demo 目录）。

依赖 ffmpeg：优先 PATH 中的 ffmpeg，其次可选依赖 ``imageio-ffmpeg``：
    backend\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements-dev.txt

常用参数：
    --course-id 9        只生成某门课的课时
    --only-missing       只处理还没有视频的课时
    --seconds 24         单个视频总时长（默认 24 秒：封面 4 + 要点各 5 + 小结 4）
    --force              重新生成已存在的文件
    --preview 1          只生成第 1 节课时，用来快速看效果
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
LESSON_VIDEO_DIR = BACKEND / "uploads" / "courses" / "lessons"

PALETTES = [
    ("0x0B3B3A", "0x14B8A6", "0xA7F3D0"),
    ("0x0B2E4F", "0x3B82F6", "0xBFDBFE"),
    ("0x1E1B4B", "0x6366F1", "0xC7D2FE"),
    ("0x14532D", "0x22C55E", "0xBBF7D0"),
    ("0x3B1D0B", "0xF97316", "0xFED7AA"),
]

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
]

LINE_CHARS = 17  # 1280 宽、32px 字号下每行约 17 个汉字


def find_ffmpeg() -> str:
    env = (os.getenv("FFMPEG_BIN") or "").strip()
    if env and Path(env).is_file():
        return env
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
        "  backend\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements-dev.txt\n"
        "也可以设置环境变量 FFMPEG_BIN 指向 ffmpeg.exe。"
    )


def find_font() -> Path:
    font = next((p for p in FONT_CANDIDATES if p.is_file()), None)
    if font is None:
        raise SystemExit("未找到中文字体，请把字体路径加到 FONT_CANDIDATES。")
    return font


def ff_path(path: Path) -> str:
    """ffmpeg 滤镜里的 Windows 路径：正斜杠 + 转义冒号。"""
    return str(path).replace("\\", "/").replace(":", "\\:")


def _visual_width(text: str) -> int:
    """估算显示宽度：汉字/全角按 2，ASCII 按 1。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


def wrap(text: str, per_line: int = LINE_CHARS, max_lines: int = 3) -> str:
    """按显示宽度折行。连续的英文字母/数字/小数点视为一个词不拆开，
    行首不出现标点；超出行数用省略号收尾。空格保留在词尾，不丢排版。"""
    text = " ".join((text or "").split())
    if not text:
        return ""

    tokens: list[str] = []
    for match in re.finditer(r"[A-Za-z0-9%.\-/]+|\S", text):
        token = match.group(0)
        start = match.start()
        spaces = ""
        j = start - 1
        while j >= 0 and text[j] == " ":
            spaces = " " + spaces
            j -= 1
        if spaces and tokens:
            tokens[-1] += spaces
        tokens.append(token)

    no_start = set("，。；、）】》.!?:;，")
    limit = per_line * 2
    lines: list[str] = []
    current = ""
    for token in tokens:
        stripped = token.rstrip()
        if (
            current
            and stripped not in no_start
            and _visual_width(current + stripped) > limit
        ):
            lines.append(current)
            current = token
            if len(lines) == max_lines:
                break
            continue
        current += token
    if current and len(lines) < max_lines:
        lines.append(current)

    consumed = sum(_visual_width(x) for x in lines)
    if len(lines) == max_lines and consumed < _visual_width(text):
        last = lines[-1]
        while _visual_width(last + "…") > limit and _visual_width(last) > 2:
            last = last[:-1]
        lines[-1] = last + "…"
    return "\n".join(lines)


def split_points(summary: str, title: str) -> list[str]:
    """把课时摘要拆成 2–3 条要点；摘要为空时用标题兜底。

    摘要常见两种排版：每行一条（· / - / 序号开头）或句号分句，都支持。
    """
    raw = (summary or "").replace("\r", "").replace("·", "\n")
    bullets: list[str] = []
    for line in raw.split("\n"):
        line = re.sub(r"^[\s\-–—•*\d.、]+", "", line.strip())
        line = line.strip(" 。；;")
        if len(line) >= 6:
            bullets.append(line)
    if not bullets:
        parts = [p.strip(" 。；;") for p in raw.replace("；", "。").split("。")]
        bullets = [p for p in parts if len(p) >= 6]
    if not bullets:
        return [f"{title}：本节讲清楚是什么、为什么、怎么做。"]
    return bullets[:3]


def build_slides(course_name: str, title: str, summary: str) -> list[tuple[str, str]]:
    points = split_points(summary, title)
    slides: list[tuple[str, str]] = [(course_name, title)]
    for i, point in enumerate(points, start=1):
        slides.append((f"本节要点 {i}/{len(points)}", point))
    slides.append(("本课小结", "按要点复习一遍，再做课后小测巩固记忆。"))
    return slides


def build_filter(
    slides: list[tuple[str, str]],
    seconds: int,
    header: str,
    footer: str,
    font: Path,
    palette_index: int,
    text_dir: Path,
    lesson_id: int,
) -> str:
    background, accent, light = PALETTES[palette_index % len(PALETTES)]
    font_q = ff_path(font)
    parts = [
        f"drawbox=x=0:y=0:w=1280:h=720:color={background}:t=fill",
        f"drawbox=x='-320+t*130':y=90:w=380:h=380:color={accent}@0.22:t=fill",
        f"drawbox=x='1080-t*110':y=420:w=430:h=200:color={accent}@0.16:t=fill",
        # 顶部课程名（封面段隐藏，避免与封面大标题重复）
        f"drawtext=fontfile='{font_q}':text='{header}':fontcolor=white@0.78:"
        "fontsize=26:x=64:y=54:enable='gte(t,4)'",
        # 底部进度条
        f"drawbox=x=0:y=714:w='iw*t/{seconds}':h=6:color={accent}:t=fill",
        f"drawtext=fontfile='{font_q}':text='{footer}':fontcolor=white@0.55:"
        "fontsize=20:x=64:y=666",
    ]

    cover = 4
    outro = 4
    point_count = max(len(slides) - 2, 1)
    point_len = max((seconds - cover - outro) / point_count, 3)

    for index, (title, body) in enumerate(slides):
        if index == 0:
            start, end = 0.0, cover
        elif index == len(slides) - 1:
            start, end = seconds - outro, seconds
        else:
            start = cover + point_len * (index - 1)
            end = start + point_len
        # 交界处留 0.05s 空隙，避免两屏文字在同帧叠加
        end = max(end - 0.05, start + 0.5)

        title_file = text_dir / f"l{lesson_id}-{index}-t.txt"
        body_file = text_dir / f"l{lesson_id}-{index}-b.txt"
        title_file.write_text(wrap(title, 24, 1), encoding="utf-8")
        body_file.write_text(wrap(body, LINE_CHARS, 3), encoding="utf-8")

        window = f"between(t,{start:.2f},{end:.2f})"
        title_size = 46 if index == 0 else 38
        title_y = "250" if index == 0 else "190"
        parts.append(
            f"drawtext=fontfile='{font_q}':textfile='{ff_path(title_file)}':"
            f"fontcolor=white:fontsize={title_size}:line_spacing=10:"
            f"x=(w-text_w)/2:y={title_y}:enable='{window}'"
        )
        parts.append(
            f"drawtext=fontfile='{font_q}':textfile='{ff_path(body_file)}':"
            f"fontcolor={light}:fontsize=32:line_spacing=16:"
            f"x=(w-text_w)/2:y=380:enable='{window}'"
        )

    parts.append("fade=t=in:st=0:d=0.4")
    parts.append(f"fade=t=out:st={max(seconds - 0.8, 0):.1f}:d=0.8")
    return ",".join(parts)


def render_video(
    ffmpeg: str,
    font: Path,
    out: Path,
    lesson_id: int,
    course_name: str,
    title: str,
    summary: str,
    seconds: int,
) -> None:
    """纯渲染：不依赖数据库，方便单独验证画面效果。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    slides = build_slides(course_name, title, summary)
    with tempfile.TemporaryDirectory() as tmp:
        vf = build_filter(
            slides=slides,
            seconds=seconds,
            header=f"COPD 健康课 · {course_name}",
            footer="小医 · 慢性阻塞性肺疾病管理",
            font=font,
            palette_index=lesson_id,
            text_dir=Path(tmp),
            lesson_id=lesson_id,
        )
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x0B2E4F:s=1280x720:r=25:d={seconds}",
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "31",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not out.is_file() or out.stat().st_size < 2000:
            raise SystemExit(
                f"生成失败：lesson {lesson_id} {title}\n{result.stderr.strip()[:1200]}"
            )

    # 抽第 2 秒作为封面，避免播放器首屏黑
    poster = out.with_suffix(".jpg")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "2",
            "-i",
            str(out),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(poster),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course-id", type=int, default=0, help="只处理某门课")
    parser.add_argument("--only-missing", action="store_true", help="只补没有视频的课时")
    parser.add_argument("--force", action="store_true", help="重新生成已有文件")
    parser.add_argument("--seconds", type=int, default=24, help="单个视频时长（秒）")
    parser.add_argument("--preview", type=int, default=0, help="只生成指定课时 id")
    args = parser.parse_args()
    seconds = min(max(args.seconds, 12), 60)

    if not os.getenv("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///" + (BACKEND / "edu.db").as_posix()

    from app.database import Base, SessionLocal, engine
    from app.models import Course, Lesson
    from app.schema_migrate import ensure_schema
    from app.seed import seed_if_empty

    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    created = 0
    attached = 0
    try:
        seed_if_empty(db)
        query = db.query(Lesson).order_by(Lesson.id)
        if args.preview:
            query = query.filter(Lesson.id == args.preview)
        elif args.course_id:
            query = query.filter(Lesson.course_id == args.course_id)
        lessons = query.all()
        if not lessons:
            raise SystemExit("数据库中没有课时，请先启动后端完成演示数据初始化。")
        ffmpeg = find_ffmpeg()
        font = find_font()
        print(f"课时 {len(lessons)} 节，输出目录：{LESSON_VIDEO_DIR}")
        for lesson in lessons:
            if args.only_missing and (lesson.video_url or "").strip():
                continue
            out = LESSON_VIDEO_DIR / f"lesson-{lesson.id}.mp4"
            if not out.is_file() or args.force:
                course = db.get(Course, lesson.course_id)
                render_video(
                    ffmpeg=ffmpeg,
                    font=font,
                    out=out,
                    lesson_id=int(lesson.id),
                    course_name=course.name if course else "COPD 课程",
                    title=lesson.title or f"第 {lesson.sort_order + 1} 课",
                    summary=lesson.summary or "",
                    seconds=seconds,
                )
                created += 1
            lesson.video_url = f"/uploads/courses/lessons/lesson-{lesson.id}.mp4"
            lesson.duration_seconds = seconds
            attached += 1
            print(f"  ✓ lesson {lesson.id} {(lesson.title or '')[:24]}（{seconds}s）")
        db.commit()
    finally:
        db.close()

    total = len(list(LESSON_VIDEO_DIR.glob("lesson-*.mp4")))
    print(f"完成：新生成 {created} 个，挂载 {attached} 节，目录内共 {total} 个视频。")


if __name__ == "__main__":
    main()
