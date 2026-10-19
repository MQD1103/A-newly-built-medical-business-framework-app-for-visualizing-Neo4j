"""从备份恢复 SQLite 业务库。

恢复前会先把当前库另存一份，避免误操作后无法回退。
请先停止后端服务，再执行：
    python backend/scripts/restore_db.py --backup backend/backups/edu-20261019-221000.db --yes
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BACKEND_DIR / "edu.db"
DEFAULT_OUT = BACKEND_DIR / "backups"


def copy_database(source: Path, target: Path) -> None:
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
        raise RuntimeError(f"数据库完整性检查失败：{result}")


def main() -> None:
    parser = argparse.ArgumentParser(description="从备份恢复小医业务数据库")
    parser.add_argument("--backup", type=Path, required=True, help="备份文件路径")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="目标数据库路径")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="恢复前快照目录")
    parser.add_argument("--yes", action="store_true", help="确认执行恢复")
    args = parser.parse_args()

    backup = args.backup.resolve()
    target = args.db.resolve()
    if not backup.exists():
        raise SystemExit(f"备份不存在：{backup}")
    if not args.yes:
        raise SystemExit("恢复会覆盖当前数据库。确认后请加 --yes 重新执行。")

    # 先验证备份本身可用
    check = sqlite3.connect(backup)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        raise SystemExit(f"备份完整性检查失败：{result}")

    if target.exists():
        args.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        snapshot = args.out_dir / f"edu-before-restore-{stamp}.db"
        copy_database(target, snapshot)
        print(f"当前库已快照：{snapshot}")

    copy_database(backup, target)
    print(f"恢复完成：{target}")
    print("请重启后端服务，并让前端强制刷新（Ctrl + F5）。")


if __name__ == "__main__":
    main()
