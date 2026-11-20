from sqlalchemy import inspect, text

from .database import engine


def _table_columns(conn, table: str) -> set[str]:
    # 用 SQLAlchemy 反射而不是 PRAGMA，SQLite / MySQL 都可复用
    return {c["name"] for c in inspect(conn).get_columns(table)}


def _ensure_unique_index(conn, table: str, index_name: str, column: str) -> None:
    """补唯一索引；MySQL 不支持 CREATE INDEX IF NOT EXISTS，先查现有索引。"""
    existing = {i["name"] for i in inspect(conn).get_indexes(table)}
    if index_name not in existing:
        conn.execute(
            text(f"CREATE UNIQUE INDEX {index_name} ON {table}({column})")
        )


def _add_columns(table: str, columns: dict[str, str]) -> None:
    """给已有 SQLite 表补列；新库由 create_all 直接建好，这里会全部跳过。"""
    with engine.begin() as conn:
        existing = _table_columns(conn, table)
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _migrate_mall_tables() -> None:
    """商城：课程/订单/权益新增字段、订单号回填、索引。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "courses" in tables:
        _add_columns(
            "courses",
            {
                "course_type": "VARCHAR(20) DEFAULT 'single'",
                "path_label": "VARCHAR(40) DEFAULT ''",
                "tagline": "VARCHAR(200) DEFAULT ''",
                "original_price": "FLOAT",
                "status": "VARCHAR(20) DEFAULT 'on'",
                "sort_order": "INTEGER DEFAULT 0",
                "valid_days": "INTEGER DEFAULT 730",
                "trial_lesson_count": "INTEGER DEFAULT 1",
                "category": "VARCHAR(40) DEFAULT ''",
                "audience": "VARCHAR(40) DEFAULT ''",
            },
        )
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE courses SET course_type='single' "
                     "WHERE course_type IS NULL OR course_type=''")
            )
            conn.execute(
                text("UPDATE courses SET status='on' "
                     "WHERE status IS NULL OR status=''")
            )
            conn.execute(
                text("UPDATE courses SET sort_order=id WHERE sort_order IS NULL")
            )
            conn.execute(
                text("UPDATE courses SET valid_days=730 "
                     "WHERE valid_days IS NULL OR valid_days<=0")
            )
            conn.execute(
                text("UPDATE courses SET trial_lesson_count=1 "
                     "WHERE trial_lesson_count IS NULL OR trial_lesson_count<0")
            )

    if "enrollments" in tables:
        _add_columns(
            "enrollments",
            {
                "order_id": "INTEGER REFERENCES course_purchases(id)",
                "source": "VARCHAR(20) DEFAULT 'seed'",
                "granted_at": "DATETIME",
                "expires_at": "DATETIME",
            },
        )
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE enrollments SET source='seed' "
                     "WHERE source IS NULL OR source=''")
            )
            conn.execute(
                text("UPDATE enrollments SET granted_at=CURRENT_TIMESTAMP "
                     "WHERE granted_at IS NULL")
            )

    if "course_purchases" in tables:
        _add_columns(
            "course_purchases",
            {
                "order_no": "VARCHAR(40) DEFAULT ''",
                "quantity": "INTEGER DEFAULT 1",
                "unit_price": "FLOAT DEFAULT 0",
                "original_amount": "FLOAT DEFAULT 0",
                "discount_amount": "FLOAT DEFAULT 0",
                "order_type": "VARCHAR(20) DEFAULT 'normal'",
                "upgrade_from_order_id": "INTEGER",
                "upgraded_to_order_id": "INTEGER",
                "transaction_id": "VARCHAR(100) DEFAULT ''",
                "valid_until": "DATETIME",
                "expires_at": "DATETIME",
                "paid_at": "DATETIME",
                "cancelled_at": "DATETIME",
                "refund_reason": "TEXT DEFAULT ''",
                "refund_amount": "FLOAT DEFAULT 0",
                "refunded_at": "DATETIME",
                "remark": "TEXT DEFAULT ''",
            },
        )
        old_order_no = ("'C-OLD-' || id" if engine.dialect.name == "sqlite"
                        else "CONCAT('C-OLD-', id)")
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE course_purchases SET order_no={old_order_no} "
                     "WHERE order_no IS NULL OR order_no=''")
            )
            conn.execute(
                text("UPDATE course_purchases SET quantity=1 "
                     "WHERE quantity IS NULL OR quantity<=0")
            )
            conn.execute(
                text("UPDATE course_purchases SET unit_price=amount "
                     "WHERE unit_price IS NULL OR unit_price=0")
            )
            conn.execute(
                text("UPDATE course_purchases SET original_amount=amount "
                     "WHERE original_amount IS NULL OR original_amount=0")
            )
            conn.execute(
                text("UPDATE course_purchases SET order_type='normal' "
                     "WHERE order_type IS NULL OR order_type=''")
            )
            conn.execute(
                text("UPDATE course_purchases SET paid_at=created_at "
                     "WHERE paid_at IS NULL AND status='paid'")
            )
            _ensure_unique_index(
                conn, "course_purchases", "ux_course_purchases_order_no", "order_no"
            )

    if "service_products" in tables:
        _add_columns(
            "service_products",
            {
                "tagline": "VARCHAR(200) DEFAULT ''",
                "original_price": "FLOAT",
                "status": "VARCHAR(20) DEFAULT 'on'",
                "sort_order": "INTEGER DEFAULT 0",
                "valid_days": "INTEGER DEFAULT 365",
            },
        )
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE service_products SET status='on' "
                     "WHERE status IS NULL OR status=''")
            )
            conn.execute(
                text("UPDATE service_products SET sort_order=id "
                     "WHERE sort_order IS NULL")
            )
            conn.execute(
                text("UPDATE service_products SET valid_days=365 "
                     "WHERE valid_days IS NULL OR valid_days<=0")
            )

    if "service_entitlements" in tables:
        _add_columns(
            "service_entitlements",
            {
                "order_id": "INTEGER REFERENCES service_purchases(id)",
                "source": "VARCHAR(20) DEFAULT 'seed'",
                "granted_at": "DATETIME",
                "expires_at": "DATETIME",
            },
        )
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE service_entitlements SET source='seed' "
                     "WHERE source IS NULL OR source=''")
            )
            conn.execute(
                text("UPDATE service_entitlements SET "
                     "granted_at=CURRENT_TIMESTAMP WHERE granted_at IS NULL")
            )

    if "service_purchases" in tables:
        _add_columns(
            "service_purchases",
            {
                "order_no": "VARCHAR(40) DEFAULT ''",
                "quantity": "INTEGER DEFAULT 1",
                "unit_price": "FLOAT DEFAULT 0",
                "original_amount": "FLOAT DEFAULT 0",
                "discount_amount": "FLOAT DEFAULT 0",
                "order_type": "VARCHAR(20) DEFAULT 'normal'",
                "transaction_id": "VARCHAR(100) DEFAULT ''",
                "valid_until": "DATETIME",
                "expires_at": "DATETIME",
                "paid_at": "DATETIME",
                "cancelled_at": "DATETIME",
                "refund_reason": "TEXT DEFAULT ''",
                "refund_amount": "FLOAT DEFAULT 0",
                "refunded_at": "DATETIME",
                "remark": "TEXT DEFAULT ''",
            },
        )
        old_order_no = ("'S-OLD-' || id" if engine.dialect.name == "sqlite"
                        else "CONCAT('S-OLD-', id)")
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE service_purchases SET order_no={old_order_no} "
                     "WHERE order_no IS NULL OR order_no=''")
            )
            conn.execute(
                text("UPDATE service_purchases SET quantity=1 "
                     "WHERE quantity IS NULL OR quantity<=0")
            )
            conn.execute(
                text("UPDATE service_purchases SET unit_price=amount "
                     "WHERE unit_price IS NULL OR unit_price=0")
            )
            conn.execute(
                text("UPDATE service_purchases SET original_amount=amount "
                     "WHERE original_amount IS NULL OR original_amount=0")
            )
            conn.execute(
                text("UPDATE service_purchases SET order_type='normal' "
                     "WHERE order_type IS NULL OR order_type=''")
            )
            conn.execute(
                text("UPDATE service_purchases SET paid_at=created_at "
                     "WHERE paid_at IS NULL AND status='paid'")
            )
            _ensure_unique_index(
                conn, "service_purchases", "ux_service_purchases_order_no", "order_no"
            )


def _migrate_feature_v2() -> None:
    """用药/检查提醒字段、错题对应课时、用药检测方式。"""
    tables = set(inspect(engine).get_table_names())

    if "reminders" in tables:
        _add_columns(
            "reminders",
            {
                "kind": "VARCHAR(20) DEFAULT 'general'",
                "drug_name": "VARCHAR(120) DEFAULT ''",
                "dosage": "VARCHAR(120) DEFAULT ''",
                "repeat_rule": "VARCHAR(20) DEFAULT 'none'",
                "check_type": "VARCHAR(120) DEFAULT ''",
                "prep_questions": "TEXT DEFAULT ''",
                "recurring_parent_id": "INTEGER",
            },
        )
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE reminders SET kind='general' "
                     "WHERE kind IS NULL OR kind=''")
            )
            conn.execute(
                text("UPDATE reminders SET repeat_rule='none' "
                     "WHERE repeat_rule IS NULL OR repeat_rule=''")
            )

    if "quiz_questions" in tables:
        _add_columns(
            "quiz_questions",
            {"lesson_id": "INTEGER REFERENCES lessons(id)"},
        )

    if "medication_checks" in tables:
        _add_columns(
            "medication_checks",
            {"mode": "VARCHAR(20) DEFAULT 'oral'"},
        )
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE medication_checks SET mode='oral' "
                     "WHERE mode IS NULL OR mode=''")
            )

    if "hospital_reminder_links" in tables and "reminders" in tables:
        # 清理历史遗留的悬空关联（提醒被删但关联仍在，SQLite 复用 id 时会撞唯一约束）
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM hospital_reminder_links "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM reminders WHERE reminders.id = "
                    "  hospital_reminder_links.reminder_id"
                    ")"
                )
            )


def ensure_schema() -> None:
    """为已有库补齐新增列。

    SQLite 老库可原地升级；MySQL 仅支持由 ``create_all`` 新建的空库，
    不负责从旧版本 MySQL 结构迁移。生产环境结构变更建议使用 Alembic。
    """
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
        # 只有 SQLite 需要重建表改可空；MySQL 新库由 create_all 直接建对。
        if (
            engine.dialect.name == "sqlite"
            and course_col is not None
            and course_col.get("nullable") is False
        ):
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

    _migrate_mall_tables()
    _migrate_feature_v2()
