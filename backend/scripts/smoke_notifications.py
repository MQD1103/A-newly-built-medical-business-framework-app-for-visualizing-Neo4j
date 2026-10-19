# -*- coding: utf-8 -*-
"""通知 / 提醒调度冒烟测试。

在临时目录建一个全新的演示库，启动真实后端进程后逐项验证：
健康检查、登录限流、提醒可见范围、7d/1d 触发档、通知偏好、完成状态、
已读与全部已读、后台调度器补发及幂等。

不会读写 backend/edu.db。用法：
    python backend/scripts/smoke_notifications.py
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TEST_DIR = Path(tempfile.mkdtemp(prefix="xiaoyi_notify_smoke_"))
DB = TEST_DIR / "smoke.db"
LOG = TEST_DIR / "server.log"
PORT = 8767
BASE = f"http://127.0.0.1:{PORT}"

checks = []


def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail and not cond else ""))


def request(method, path, token=None, body=None, timeout=20):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload, dict(exc.headers)


def login(username, password):
    return request("POST", "/api/auth/login", body={"username": username, "password": password})


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def wait_for_health(seconds=40):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            status, payload, _ = request("GET", "/api/health")
            if status == 200:
                return payload
        except Exception:
            pass
        time.sleep(0.5)
    raise SystemExit("服务未能启动，查看 " + str(LOG))


def main():
    # 全新库：启动时自动建表并灌入演示数据
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
    env["JWT_SECRET_KEY"] = "phase2-test-secret"
    env["REMINDER_SCAN_SECONDS"] = "3"
    env["LOGIN_RATE_LIMIT"] = "3"
    env["LOGIN_RATE_WINDOW_SECONDS"] = "60"
    env["LOGIN_IP_LIMIT"] = "1000"
    env["PYTHONIOENCODING"] = "utf-8"
    log_file = open(LOG, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(BACKEND), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    try:
        health = wait_for_health()
        check("健康检查返回 ok", health.get("status") == "ok", str(health))
        check("健康检查确认数据库可用", health.get("database") == "ok", str(health))

        # 建表校验
        con = sqlite3.connect(DB)
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        users = con.execute("select count(*) from users").fetchone()[0]
        con.close()
        check("启动后存在 notifications 表", "notifications" in tables)
        check("启动后存在 reminder_completions 表", "reminder_completions" in tables)
        check("演示数据已灌入", users >= 4, f"users={users}")

        # 登录
        st, payload, _ = login("admin", "admin123")
        check("管理员登录", st == 200 and payload.get("access_token"), str(payload))
        admin_t = payload["access_token"]
        st, payload, _ = login("t1001", "teach123")
        check("教师登录", st == 200 and payload.get("access_token"))
        teacher_t = payload["access_token"]
        st, payload, _ = login("s2024001", "stu123")
        check("学习者1登录", st == 200 and payload.get("access_token"))
        s1_t = payload["access_token"]
        st, payload, _ = login("s2024002", "stu123")
        check("学习者2登录", st == 200 and payload.get("access_token"))
        s2_t = payload["access_token"]

        # 登录限流：第 4 次同用户名失败应 429
        statuses = []
        retry_header = None
        for _ in range(4):
            st, payload, headers = login("no_such_probe_user", "wrong-pass")
            statuses.append(st)
            if st == 429:
                retry_header = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
        check("登录失败 3 次后触发 429", statuses == [401, 401, 401, 429], str(statuses))
        check("429 返回 Retry-After", bool(retry_header and int(retry_header) > 0), str(retry_header))
        # 正常账号不受影响
        st, payload, _ = login("s2024001", "stu123")
        check("限流不影响其他账号登录", st == 200)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 选一门学习者1有、学习者2没有学习权的课程
        st, courses1, _ = request("GET", "/api/courses", token=s1_t)
        st2, courses2, _ = request("GET", "/api/courses", token=s2_t)
        check("课程列表可访问", st == 200 and st2 == 200)
        s2_enrolled = {c["id"] for c in courses2 if c.get("enrolled")}
        target = next((c for c in courses1 if c.get("enrolled") and c["id"] not in s2_enrolled), None)
        check("找到学习者1有、学习者2无的课程", target is not None)
        if target is None:
            raise SystemExit("演示数据中缺少可对比课程")
        course_id = target["id"]

        # 提醒A：30 秒后到期 → 1d 档
        st, rem_a, _ = request("POST", "/api/reminders", token=teacher_t, body={
            "title": "阶段二测试提醒A",
            "content": "测试提前一天通知",
            "due_at": iso(now + timedelta(seconds=30)),
            "course_id": course_id,
        })
        check("教师创建课程提醒A", st == 200 and rem_a.get("source") == "manager", str(rem_a))
        rem_a_id = rem_a["id"]

        st, inbox1, _ = request("GET", "/api/notifications?unread_only=true&page_size=100", token=s1_t)
        item_a = next((n for n in inbox1["items"] if n["reminder_id"] == rem_a_id), None)
        check("学习者1收到提醒A通知", item_a is not None)
        check("提醒A触发档位为 1d", item_a and item_a["trigger_key"] == "1d", str(item_a))
        check("通知正文带到期提示", item_a and "明天到期" in item_a["body"], str(item_a and item_a["body"]))
        check("通知带课程名", item_a and item_a["course_name"] != "")

        st, inbox2, _ = request("GET", "/api/notifications?page_size=100", token=s2_t)
        check("未报名学习者2收不到该课程提醒", all(n["reminder_id"] != rem_a_id for n in inbox2["items"]))

        st, summary1, _ = request("GET", "/api/notifications/summary", token=s1_t)
        st, home1, _ = request("GET", "/api/home", token=s1_t)
        check("首页未读数与通知汇总一致", home1.get("unread_notifications") == summary1.get("unread"),
              f"home={home1.get('unread_notifications')} summary={summary1.get('unread')}")

        # 单条已读
        st, read_one, _ = request("POST", f"/api/notifications/{item_a['id']}/read", token=s1_t)
        check("标记单条通知已读", st == 200 and read_one.get("read") is True)
        st, summary_after, _ = request("GET", "/api/notifications/summary", token=s1_t)
        check("未读数减一", summary_after.get("unread") == summary1.get("unread") - 1,
              f"{summary1.get('unread')} -> {summary_after.get('unread')}")
        st, forbidden, _ = request("POST", f"/api/notifications/{item_a['id']}/read", token=s2_t)
        check("不能操作他人通知", st == 403, f"status={st}")

        # 提醒B：3 天后 → 7d 档；关闭提醒后不再新增 1d 通知
        st, rem_b, _ = request("POST", "/api/reminders", token=teacher_t, body={
            "title": "阶段二测试提醒B",
            "content": "测试偏好与完成",
            "due_at": iso(now + timedelta(days=3)),
            "course_id": course_id,
        })
        rem_b_id = rem_b["id"]
        st, inbox1, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
        item_b7 = next((n for n in inbox1["items"] if n["reminder_id"] == rem_b_id and n["trigger_key"] == "7d"), None)
        check("提醒B生成 7d 通知", item_b7 is not None)

        st, pref, _ = request("PUT", f"/api/reminders/{rem_b_id}/notify", token=s1_t, body={"enabled": False})
        check("学习者可关闭提醒B通知", st == 200 and pref.get("notify_enabled") is False)
        st, _, _ = request("PATCH", f"/api/reminders/{rem_b_id}", token=teacher_t, body={
            "title": "阶段二测试提醒B-改",
            "due_at": iso(now + timedelta(hours=12)),
        })
        check("教师更新提醒B", st == 200)
        st, inbox1, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
        check("关闭通知后不再生成 1d 通知",
              all(not (n["reminder_id"] == rem_b_id and n["trigger_key"] == "1d") for n in inbox1["items"]))

        st, _, _ = request("PUT", f"/api/reminders/{rem_b_id}/notify", token=s1_t, body={"enabled": True})
        st, _, _ = request("PATCH", f"/api/reminders/{rem_b_id}", token=teacher_t, body={"title": "阶段二测试提醒B-再改"})
        st, inbox1, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
        check("重新开启后可补发 1d 通知",
              any(n["reminder_id"] == rem_b_id and n["trigger_key"] == "1d" for n in inbox1["items"]))

        # 完成：本人完成，通知转已读，首页不再显示
        st, done, _ = request("POST", f"/api/reminders/{rem_b_id}/complete", token=s1_t, body={"completed": True})
        check("学习者标记提醒B完成", st == 200 and done.get("completed") is True)
        st, inbox1, _ = request("GET", "/api/notifications?unread_only=true&page_size=100", token=s1_t)
        check("完成后该提醒通知不再未读",
              all(n["reminder_id"] != rem_b_id for n in inbox1["items"]))
        st, rems1, _ = request("GET", "/api/reminders", token=s1_t)
        rb1 = next((r for r in rems1 if r["id"] == rem_b_id), None)
        check("提醒列表显示本人已完成", rb1 and rb1.get("completed") is True)
        st, rems2, _ = request("GET", "/api/reminders", token=s2_t)
        rb2 = next((r for r in rems2 if r["id"] == rem_b_id), None)
        check("完成状态不串号", rb2 is None or rb2.get("completed") is False)
        st, home1, _ = request("GET", "/api/home", token=s1_t)
        check("首页临近提醒排除已完成", all(r["id"] != rem_b_id for r in home1.get("upcoming_reminders", [])))
        st, undone, _ = request("POST", f"/api/reminders/{rem_b_id}/complete", token=s1_t, body={"completed": False})
        check("可取消完成状态", st == 200 and undone.get("completed") is False)

        # 调度器：先建 10 天后的提醒（不触发），再直接改库到 2 天后，等后台扫描补发
        st, rem_c, _ = request("POST", "/api/reminders", token=teacher_t, body={
            "title": "阶段二调度器测试",
            "content": "由后台任务补发",
            "due_at": iso(now + timedelta(days=10)),
            "course_id": course_id,
        })
        rem_c_id = rem_c["id"]
        st, inbox1, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
        check("10 天后提醒暂不生成通知", all(n["reminder_id"] != rem_c_id for n in inbox1["items"]))

        new_due = (now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S.%f")
        for attempt in range(10):
            try:
                con = sqlite3.connect(DB, timeout=5)
                con.execute("update reminders set due_at=? where id=?", (new_due, rem_c_id))
                con.commit()
                con.close()
                break
            except sqlite3.OperationalError:
                time.sleep(0.5)
        found = False
        for _ in range(12):
            time.sleep(1)
            st, inbox1, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
            if any(n["reminder_id"] == rem_c_id for n in inbox1["items"]):
                found = True
                break
        check("后台调度器自动补发通知", found)
        before = sum(1 for n in inbox1["items"] if n["reminder_id"] == rem_c_id)
        time.sleep(7)  # 再跨过两个扫描周期
        st, inbox1, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
        after = sum(1 for n in inbox1["items"] if n["reminder_id"] == rem_c_id)
        check("同一档位通知不重复生成", before == after == 1, f"before={before} after={after}")

        # 全部已读
        st, result, _ = request("POST", "/api/notifications/read-all", token=s1_t)
        check("一键全部已读", st == 200 and result.get("ok") is True)
        st, summary1, _ = request("GET", "/api/notifications/summary", token=s1_t)
        check("全部已读后未读数为 0", summary1.get("unread") == 0, str(summary1.get("unread")))

        # 无 token 访问
        st, _, _ = request("GET", "/api/notifications")
        check("通知接口需要登录", st in (401, 403), f"status={st}")

        # 清理测试提醒（教师提醒为 manager，不可删除；用管理员也无删除接口，保留在副本库）
        print(f"\n测试库：{DB}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()

    shutil.rmtree(TEST_DIR, ignore_errors=True)
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\n结果：{passed}/{len(checks)} 通过")
    if passed != len(checks):
        print("\n失败项：")
        for name, ok, detail in checks:
            if not ok:
                print(" -", name, detail)
        sys.exit(1)


if __name__ == "__main__":
    main()
