"""重建演示数据库（会清空现有业务数据，请先确认）。

执行前会自动把现有库快照到 backend/backups/，然后重新建表、跑迁移、灌入演示数据。

用法：
    python backend/scripts/rebuild_demo_db.py --yes
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BACKEND_DIR / "edu.db"
DEFAULT_OUT = BACKEND_DIR / "backups"


def snapshot(source: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"edu-before-rebuild-{stamp}.db"
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()
    check = sqlite3.connect(target)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        raise RuntimeError("重建前快照完整性检查失败，已中止")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="重建小医演示数据库")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="目标数据库路径")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="重建前快照目录")
    parser.add_argument("--yes", action="store_true", help="确认清空并重建")
    args = parser.parse_args()

    target = args.db.resolve()
    if not args.yes:
        raise SystemExit("重建会清空现有数据。确认后请加 --yes 重新执行。")

    if target.exists():
        saved = snapshot(target, args.out_dir.resolve())
        print(f"现有库已快照：{saved}")
        target.unlink()
        target.with_suffix(target.suffix + "-wal").unlink(missing_ok=True)
        target.with_suffix(target.suffix + "-shm").unlink(missing_ok=True)

    # 必须在导入 app 模块前固定数据库地址，避免回落到 CWD 下的 edu.db
    os.environ["DATABASE_URL"] = f"sqlite:///{target.as_posix()}"
    sys.path.insert(0, str(BACKEND_DIR))

    from app.database import Base, SessionLocal, engine  # noqa: E402
    from app.schema_migrate import ensure_schema  # noqa: E402
    from app.seed import seed_if_empty  # noqa: E402
    from app.models import Course, Lesson, ServiceProduct, User  # noqa: E402

    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        counts = {
            "用户": db.query(User).count(),
            "课程": db.query(Course).count(),
            "课时": db.query(Lesson).count(),
            "服务商品": db.query(ServiceProduct).count(),
        }
    finally:
        db.close()

    if counts["课程"] <= 0 or counts["用户"] <= 0:
        raise SystemExit("重建后数据为空，请检查 seed 逻辑")
    print("重建完成：" + "，".join(f"{k} {v}" for k, v in counts.items()))
    print(f"数据库：{target}")


if __name__ == "__main__":
    main()
