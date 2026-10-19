"""备份 SQLite 业务库（在线安全备份，不复制 -wal 中间态）。

用法（在任意目录执行都可以）：
    python backend/scripts/backup_db.py
    python backend/scripts/backup_db.py --keep 30
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BACKEND_DIR / "edu.db"
DEFAULT_OUT = BACKEND_DIR / "backups"


def backup_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
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
        target.unlink(missing_ok=True)
        raise RuntimeError(f"备份完整性检查失败：{result}")


def prune(out_dir: Path, keep: int) -> list[Path]:
    files = sorted(out_dir.glob("edu-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for path in files[keep:]:
        path.unlink(missing_ok=True)
        removed.append(path)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="备份小医业务数据库")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="源数据库路径")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="备份目录")
    parser.add_argument("--keep", type=int, default=14, help="保留最近几份备份")
    args = parser.parse_args()

    source = args.db.resolve()
    if not source.exists():
        raise SystemExit(f"数据库不存在：{source}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = args.out_dir.resolve() / f"edu-{stamp}.db"
    backup_database(source, target)
    removed = prune(args.out_dir.resolve(), max(1, args.keep))

    size_mb = target.stat().st_size / 1024 / 1024
    print(f"备份完成：{target}（{size_mb:.2f} MB）")
    if removed:
        print(f"已清理旧备份 {len(removed)} 份，保留最近 {args.keep} 份")
    print("提示：备份文件含业务数据，不要提交到 Git 或发给无关人员。")


if __name__ == "__main__":
    main()
