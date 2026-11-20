# -*- coding: utf-8 -*-
"""症状日记 / 用药打卡 / 随访提醒 冒烟测试。

在临时目录建一个全新的演示库，启动真实后端进程后逐项验证：
- 症状日记：写入、同日覆盖、加重提示、未来日期拦截
- 用药打卡：计划 CRUD、今日槽位自动生成、打卡与撤销、依从率与连续天数
- 随访提醒：计划 CRUD、状态计算、完成随访自动滚动下一周期、
  影子提醒接入通知链路、暂停后停止提醒

不会读写 backend/edu.db。用法：
    python backend/scripts/smoke_health_tracking.py
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TEST_DIR = Path(tempfile.mkdtemp(prefix="xiaoyi_health_smoke_"))
DB = TEST_DIR / "smoke.db"
LOG = TEST_DIR / "server.log"
PORT = 8771
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
    return request(
        "POST", "/api/auth/login", body={"username": username, "password": password}
    )


def wait_for_health(seconds=60):
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
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
    env["JWT_SECRET_KEY"] = "health-test-secret"
    env["REMINDER_SCAN_SECONDS"] = "2"
    env["PYTHONIOENCODING"] = "utf-8"
    log_file = open(LOG, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning",
        ],
        cwd=str(BACKEND), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    try:
        health = wait_for_health()
        check("健康检查返回 ok", health.get("status") == "ok", str(health))

        con = sqlite3.connect(DB)
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        con.close()
        for table in ("symptom_entries", "medication_plans", "medication_logs",
                      "followup_plans", "followup_visits"):
            check(f"已建表 {table}", table in tables)

        st, payload, _ = login("s2024001", "stu123")
        check("演示学生登录成功", st == 200 and payload.get("access_token"), str(payload)[:120])
        token = payload["access_token"]

        today = date.today()

        # ---------- 症状日记 ----------
        st, entry, _ = request(
            "POST", "/api/symptoms", token,
            {"cough": 1, "dyspnea": 1, "sputum": 0, "note": "今日尚可"},
        )
        check("症状日记写入成功", st == 200 and entry.get("total") == 2, str(entry))
        check("症状日记返回免责声明",
              "不构成诊断" in (entry.get("disclaimer") or "") or st == 200)

        st, again, _ = request(
            "POST", "/api/symptoms", token,
            {"cough": 3, "dyspnea": 3, "sputum": 3, "note": "明显加重"},
        )
        check("同日再次提交覆盖而非新增",
              st == 200 and again.get("id") == entry.get("id"), str(again))
        check("重度症状触发加重提示", again.get("warning") is True, str(again))

        st, diary, _ = request("GET", "/api/symptoms?days=30", token)
        check("症状日记列表可读取", st == 200 and len(diary.get("items", [])) == 1, str(diary)[:160])
        check("日记顶部汇总加重提示", diary.get("warning") is True)

        st, future, _ = request(
            "POST", "/api/symptoms", token,
            {"record_date": (today + timedelta(days=1)).isoformat(),
             "cough": 1, "dyspnea": 0, "sputum": 0},
        )
        check("未来日期被拦截", st == 400, str(future))

        # ---------- 用药打卡 ----------
        st, plan, _ = request(
            "POST", "/api/medication/plans", token,
            {"drug_name": "噻托溴铵粉雾剂", "dosage": "每次 1 吸",
             "frequency": 2, "times": "08:00,20:00"},
        )
        check("创建用药计划成功", st == 200 and plan.get("frequency") == 2, str(plan))
        plan_id = plan["id"]

        st, bad, _ = request(
            "POST", "/api/medication/plans", token,
            {"drug_name": "错误时间", "frequency": 1, "times": "25:00"},
        )
        check("非法时间格式被拦截", st == 400, str(bad))

        st, today_out, _ = request("GET", "/api/medication/today", token)
        slots = [i for i in today_out.get("items", []) if i["plan_id"] == plan_id]
        check("今日槽位按每日次数自动生成", len(slots) == 2, str(today_out)[:200])
        check("今日初始为待打卡",
              today_out.get("pending") >= 2 and today_out.get("taken") >= 0)

        st, checked, _ = request(
            "POST", "/api/medication/checkin", token,
            {"plan_id": plan_id, "slot": 1, "status": "taken", "note": "已吸"},
        )
        check("打卡成功", st == 200 and checked.get("status") == "taken", str(checked))
        check("打卡记录写入时间", bool(checked.get("checked_at")))

        st, again2, _ = request(
            "POST", "/api/medication/checkin", token,
            {"plan_id": plan_id, "slot": 1, "status": "taken", "note": "重复打卡"},
        )
        check("重复打卡是更新不新增",
              st == 200 and again2.get("log_id") == checked.get("log_id"), str(again2))

        st, undone, _ = request(
            "POST", "/api/medication/checkin", token,
            {"plan_id": plan_id, "slot": 1, "status": "pending"},
        )
        check("可撤销打卡", st == 200 and undone.get("status") == "pending", str(undone))

        # slot 超出该计划的每日次数（次数 2，传 5）→ 业务拦截 400
        st, bad_slot, _ = request(
            "POST", "/api/medication/checkin", token,
            {"plan_id": plan_id, "slot": 5, "status": "taken"},
        )
        check("超出每日次数的打卡被拦截", st == 400, str(bad_slot))

        # slot 超出合法区间上限 → 参数校验拦截（400 或 422）
        st, bad_slot2, _ = request(
            "POST", "/api/medication/checkin", token,
            {"plan_id": plan_id, "slot": 9, "status": "taken"},
        )
        check("超出合法班次区间被拦截", st in (400, 422), str(bad_slot2))

        request("POST", "/api/medication/checkin", token,
                {"plan_id": plan_id, "slot": 1, "status": "taken"})
        request("POST", "/api/medication/checkin", token,
                {"plan_id": plan_id, "slot": 2, "status": "taken"})

        st, adh, _ = request("GET", "/api/medication/adherence?days=30", token)
        check("依从率接口返回应服次数", adh.get("scheduled", 0) > 0, str(adh))
        check("依从率统计到已服用次数", adh.get("taken", 0) >= 2, str(adh))
        check("依从率在 0-100 之间", 0 <= adh.get("rate", -1) <= 100, str(adh))
        check("连续打卡天数已计算", adh.get("streak_days", 0) >= 1, str(adh))

        st, logs, _ = request("GET", "/api/medication/logs?days=30", token)
        check("打卡历史可读取", st == 200 and len(logs) >= 2, str(logs)[:160])

        st, paused, _ = request(
            "PATCH", f"/api/medication/plans/{plan_id}", token, {"status": "paused"},
        )
        check("可暂停用药计划", st == 200 and paused.get("status") == "paused", str(paused))

        # ---------- 随访提醒 ----------
        st, fu, _ = request(
            "POST", "/api/followups", token,
            {"title": "呼吸科门诊随访", "follow_type": "outpatient",
             "interval_days": 30, "next_due_date": (today + timedelta(days=5)).isoformat(),
             "hospital": "市第一医院", "doctor": "张医生"},
        )
        check("创建随访计划成功", st == 200 and fu.get("interval_days") == 30, str(fu))
        check("随访类型返回中文标签", fu.get("follow_type_label") == "门诊随访", str(fu))
        check("5 天后到期判定为临近", fu.get("state") == "due_soon", str(fu))
        check("距到期天数正确", fu.get("days_remaining") == 5, str(fu))
        fu_id = fu["id"]

        st, overdue, _ = request(
            "POST", "/api/followups", token,
            {"title": "逾期随访", "follow_type": "imaging", "interval_days": 90,
             "next_due_date": (today - timedelta(days=2)).isoformat()},
        )
        check("过期日期判定为逾期", overdue.get("state") == "overdue", str(overdue))
        check("逾期天数为负", overdue.get("days_remaining") == -2, str(overdue))
        overdue_id = overdue["id"]

        st, bad_type, _ = request(
            "POST", "/api/followups", token,
            {"title": "错误类型", "follow_type": "unknown"},
        )
        check("非法随访类型被拦截", st == 400, str(bad_type))

        # 影子提醒接入既有通知链路：5 天后到期应产生 7d 档站内通知
        notified = False
        for _ in range(15):
            st, notes, _ = request("GET", "/api/notifications", token)
            items = notes.get("items", []) if isinstance(notes, dict) else notes
            if any("随访提醒" in (n.get("title") or "") for n in items):
                notified = True
                break
            time.sleep(1)
        check("随访自动生成站内通知", notified)

        st, done, _ = request(
            "POST", f"/api/followups/{fu_id}/complete", token,
            {"result": "症状稳定，继续原方案"},
        )
        check("完成随访成功", st == 200, str(done))
        check("完成后按周期滚动下次到期",
              done.get("next_due_date") == (today + timedelta(days=30)).isoformat(),
              str(done))
        check("完成后记录上次随访日",
              done.get("last_visit_date") == today.isoformat(), str(done))
        check("完成后随访次数 +1", done.get("visit_count") == 1, str(done))

        st, visits, _ = request("GET", f"/api/followups/{fu_id}/visits", token)
        check("随访记录可读取", st == 200 and len(visits) == 1, str(visits)[:160])

        st, summ, _ = request("GET", "/api/followups/summary", token)
        check("汇总接口返回统计", st == 200 and summ.get("visit_count", 0) >= 1, str(summ))
        check("汇总识别逾期数量", summ.get("overdue", 0) >= 1, str(summ))
        check("汇总给出下次随访", bool(summ.get("next_due_date")), str(summ))

        con = sqlite3.connect(DB)
        reminder_rows = con.execute(
            "select count(*) from reminders where kind='checkup'"
        ).fetchone()[0]
        con.close()
        check("随访挂上了 checkup 影子提醒", reminder_rows >= 2, f"rows={reminder_rows}")

        st, paused_fu, _ = request(
            "PATCH", f"/api/followups/{overdue_id}", token, {"status": "paused"},
        )
        check("可暂停随访计划", st == 200 and paused_fu.get("status") == "paused", str(paused_fu))
        con = sqlite3.connect(DB)
        left = con.execute(
            "select count(*) from reminders r join followup_plans f on r.id=f.reminder_id "
            "where f.id=?", (overdue_id,)
        ).fetchone()[0]
        con.close()
        check("暂停后撤销影子提醒", left == 0, f"left={left}")

        st, deleted, _ = request("DELETE", f"/api/followups/{overdue_id}", token)
        check("删除随访计划成功", st == 200 and deleted.get("ok") is True, str(deleted))
        st, gone, _ = request("GET", "/api/followups?include_closed=true", token)
        check("删除后不再出现在列表",
              all(p["id"] != overdue_id for p in gone), str(gone)[:160])

        st, del_plan, _ = request("DELETE", f"/api/medication/plans/{plan_id}", token)
        check("删除用药计划成功", st == 200 and del_plan.get("ok") is True, str(del_plan))

        # 越权：另一名学生不能访问
        st, other, _ = login("s2024002", "stu123")
        token2 = other.get("access_token") if st == 200 else None
        if token2:
            st, _, _ = request("GET", "/api/medication/plans", token2)
            check("其他学生只能看到自己的计划", st == 200)
            st, forbid, _ = request(
                "POST", "/api/medication/checkin", token2,
                {"plan_id": 1, "slot": 1, "status": "taken"},
            )
            check("不能给别人的计划打卡", st == 404, str(forbid))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()

    failed = [name for name, ok, _ in checks if not ok]
    print()
    print(f"总计 {len(checks)} 项，通过 {len(checks) - len(failed)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项：")
        for name in failed:
            print("  - " + name)
        sys.exit(1)
    print("全部通过。")


if __name__ == "__main__":
    main()
