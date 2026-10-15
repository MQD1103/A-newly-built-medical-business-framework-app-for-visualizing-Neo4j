from sqlalchemy import inspect, text

from .database import engine


def ensure_schema() -> None:
    """为已有 SQLite 库补齐新增列。"""
    insp = inspect(engine)
    tables = insp.get_table_names()
    if "users" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "avatar_url" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) DEFAULT ''")
            )

    if "reminders" in tables:
        rem_cols = {c["name"] for c in insp.get_columns("reminders")}
        if "source" not in rem_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE reminders ADD COLUMN source VARCHAR(20) "
                        "DEFAULT 'manager'"
                    )
                )
                # 已有种子/管理端数据视为系统或管理者；无 creator 区分时统一标 system
                conn.execute(text("UPDATE reminders SET source = 'system'"))
        # SQLite 无法直接改 NOT NULL；重建表使 course_id 可空
        rem_cols = {c["name"] for c in insp.get_columns("reminders")}
        course_col = next(
            (c for c in insp.get_columns("reminders") if c["name"] == "course_id"),
            None,
        )
        if course_col is not None and course_col.get("nullable") is False:
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE reminders_new (
                          id INTEGER NOT NULL PRIMARY KEY,
                          course_id INTEGER,
                          title VARCHAR(200) NOT NULL,
                          content TEXT NOT NULL DEFAULT '',
                          due_at DATETIME NOT NULL,
                          external_url VARCHAR(500) DEFAULT '',
                          creator_id INTEGER NOT NULL,
                          source VARCHAR(20) DEFAULT 'manager',
                          created_at DATETIME,
                          FOREIGN KEY(course_id) REFERENCES courses (id),
                          FOREIGN KEY(creator_id) REFERENCES users (id)
                        )
                        """
                    )
                )
                cols = [
                    "id",
                    "course_id",
                    "title",
                    "content",
                    "due_at",
                    "external_url",
                    "creator_id",
                    "created_at",
                ]
                if "source" in rem_cols:
                    cols.insert(-1, "source")
                col_sql = ", ".join(cols)
                conn.execute(
                    text(
                        f"INSERT INTO reminders_new ({col_sql}) "
                        f"SELECT {col_sql} FROM reminders"
                    )
                )
                conn.execute(text("DROP TABLE reminders"))
                conn.execute(text("ALTER TABLE reminders_new RENAME TO reminders"))
                conn.execute(text("PRAGMA foreign_keys=ON"))

        # 管理员为指定用户下发的提醒（可空；必须放在上面重建表之后，
        # 因为重建分支用的是固定列清单，会建出不带该列的新表）
        rem_cols = {c["name"] for c in insp.get_columns("reminders")}
        if "target_user_id" not in rem_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE reminders ADD COLUMN target_user_id INTEGER "
                        "REFERENCES users(id)"
                    )
                )

    if "community_posts" in tables:
        post_cols = {c["name"] for c in insp.get_columns("community_posts")}
        if "image_urls" not in post_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE community_posts ADD COLUMN image_urls TEXT "
                        "DEFAULT '[]'"
                    )
                )
        if "original_post_id" not in post_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE community_posts ADD COLUMN original_post_id "
                        "INTEGER REFERENCES community_posts(id)"
                    )
                )

    if "notices" in tables:
        notice_cols = {c["name"] for c in insp.get_columns("notices")}
        if "is_urgent" not in notice_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE notices ADD COLUMN is_urgent BOOLEAN "
                        "DEFAULT 0"
                    )
                )

    if "courses" in tables:
        course_cols = {c["name"] for c in insp.get_columns("courses")}
        if "price" not in course_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE courses ADD COLUMN price FLOAT "
                        "DEFAULT 2.99"
                    )
                )
        if "cover_url" not in course_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE courses ADD COLUMN cover_url VARCHAR(500) "
                        "DEFAULT ''"
                    )
                )
