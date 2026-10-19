"""医院对接冒烟测试。

在临时目录新建演示库，启动真实后端和一个本地假医院接口，验证：
合作医院开通、用户授权、只读资料同步与缓存、照护者授权、撤销授权、
医嘱转提醒、演示 / HTTP 两种模式、上游错误处理与患者标识脱敏。

不会读写 backend/edu.db。用法：
    python backend/scripts/smoke_hospital.py
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TEST_DIR = Path(tempfile.mkdtemp(prefix="xiaoyi_hospital_smoke_"))
DB = TEST_DIR / "smoke.db"
LOG = TEST_DIR / "server.log"
PORT = 8768
BASE = f"http://127.0.0.1:{PORT}"
REMOTE_TOKEN = "test-hospital-token"

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


class FakeHospital(BaseHTTPRequestHandler):
    fail = False

    def do_GET(self):  # noqa: N802
        parts = [urllib.parse.unquote(p) for p in self.path.strip("/").split("/")]
        if len(parts) != 3 or parts[0] != "patients" or parts[2] != "records":
            self.send_error(404)
            return
        if self.headers.get("Authorization") != f"Bearer {REMOTE_TOKEN}":
            self.send_error(401)
            return
        patient_ref = parts[1]
        if FakeHospital.fail:
            self.send_error(500)
            return
        if patient_ref.startswith("UNKNOWN"):
            self.send_error(404)
            return
        items = [
            {
                "external_id": "remote-advice-1",
                "record_type": "advice",
                "title": "远程医院复诊嘱托",
                "content": "按医嘱用药，按时复诊。",
                "doctor_name": "远程医生",
                "department": "呼吸内科",
                "occurred_at": "2026-10-01T09:00:00",
            },
            {
                "external_id": "remote-record-1",
                "record_type": "record",
                "title": "远程检查摘要",
                "content": "结果以医院报告为准。",
                "doctor_name": "远程医生",
                "department": "呼吸内科",
                "occurred_at": "2026-09-20",
            },
        ]
        raw = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


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
    # 让系统分配空闲端口，避免与本机其他软件固定端口冲突
    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeHospital)
    fake_base = f"http://127.0.0.1:{fake.server_address[1]}"
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
    env["JWT_SECRET_KEY"] = "hospital-smoke-secret"
    env["REMINDER_SCAN_SECONDS"] = "60"
    env["HOSPITAL_API_BASE_URL"] = fake_base
    env["HOSPITAL_API_TOKEN"] = REMOTE_TOKEN
    env["HOSPITAL_API_TIMEOUT_SECONDS"] = "3"
    env["HOSPITAL_SYNC_LIMIT"] = "50"
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

        con = sqlite3.connect(DB)
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        con.close()
        check("启动后存在医院对接相关表",
              {"hospital_partners", "hospital_authorizations", "hospital_records",
               "hospital_caregiver_grants", "hospital_reminder_links"} <= tables)

        tokens = {}
        for name, username, password in (
            ("admin", "admin", "admin123"),
            ("teacher", "t1001", "teach123"),
            ("s1", "s2024001", "stu123"),
            ("s2", "s2024002", "stu123"),
        ):
            st, payload, _ = login(username, password)
            check(f"{name} 登录", st == 200 and payload.get("access_token"))
            tokens[name] = payload["access_token"]
        admin_t, teacher_t, s1_t, s2_t = (
            tokens["admin"], tokens["teacher"], tokens["s1"], tokens["s2"]
        )

        st, _, _ = request("GET", "/api/hospital/partners")
        check("医院接口需要登录", st in (401, 403), f"status={st}")

        st, partners, _ = request("GET", "/api/hospital/partners", token=s1_t)
        demo = next((p for p in partners if p["code"] == "demo-hospital"), None)
        check("演示医院已开通并可见", st == 200 and demo is not None, str(partners))
        demo_id = demo["id"]

        st, _, _ = request("POST", "/api/hospital/admin/partners", token=teacher_t, body={
            "code": "remote-test", "name": "远程测试医院", "mode": "http",
        })
        check("非管理员不能开通医院", st == 403, f"status={st}")

        st, remote, _ = request("POST", "/api/hospital/admin/partners", token=admin_t, body={
            "code": "remote-test", "name": "远程测试医院", "mode": "http",
            "department": "呼吸内科",
        })
        check("管理员开通 HTTP 模式医院", st == 200 and remote.get("mode") == "http", str(remote))
        remote_id = remote["id"]
        st, payload, _ = request("POST", "/api/hospital/admin/partners", token=admin_t, body={
            "code": "remote-test", "name": "重复编码", "mode": "demo",
        })
        check("医院编码重复被拒绝", st == 400, f"status={st}")

        st, _, _ = request("POST", "/api/hospital/authorizations", token=s1_t, body={
            "partner_id": demo_id, "patient_ref": "P2024001XYZ", "consent": False,
        })
        check("未确认授权不能提交", st == 400, f"status={st}")

        st, auth, _ = request("POST", "/api/hospital/authorizations", token=s1_t, body={
            "partner_id": demo_id, "patient_ref": "P2024001XYZ", "consent": True,
        })
        check("用户授权演示医院", st == 200 and auth.get("status") == "active", str(auth))
        auth_id = auth["id"]
        raw_ref = "P2024001XYZ"
        check("授权响应脱敏患者标识", raw_ref not in json.dumps(auth, ensure_ascii=False), str(auth))
        check("授权包含三类只读范围", set(auth.get("scopes") or []) == {"advice", "condition", "record"})

        st, records, _ = request("GET", "/api/hospital/records", token=s1_t)
        check("同步前没有缓存资料", st == 200 and records == [], str(records))

        st, sync, _ = request("POST", f"/api/hospital/authorizations/{auth_id}/sync", token=s1_t)
        check("同步演示医院资料", st == 200 and sync.get("added") == 3 and sync.get("total") == 3, str(sync))
        st, records, _ = request("GET", "/api/hospital/records", token=s1_t)
        check("只读资料已缓存", st == 200 and len(records) == 3, str(len(records)))
        check("资料覆盖嘱托/病情/病历摘要",
              {r["record_type"] for r in records} == {"advice", "condition", "record"})
        advice = next(r for r in records if r["record_type"] == "advice")
        st, detail, _ = request("GET", f"/api/hospital/records/{advice['id']}", token=s1_t)
        check("本人可查看资料详情", st == 200 and detail.get("id") == advice["id"])

        st, _, _ = request("GET", f"/api/hospital/records/{advice['id']}", token=s2_t)
        check("无关用户不能查看资料", st == 403, f"status={st}")
        st, records2, _ = request("GET", "/api/hospital/records", token=s2_t)
        check("无关用户资料列表为空", st == 200 and records2 == [], str(records2))

        due = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
        st, made, _ = request("POST", f"/api/hospital/records/{advice['id']}/reminder", token=s1_t, body={
            "due_at": iso(due), "title": "按医院嘱托复查",
        })
        check("医生嘱托可转成个人提醒", st == 200 and made.get("reminder_id"), str(made))
        reminder_id = made["reminder_id"]
        st, rems, _ = request("GET", "/api/reminders", token=s1_t)
        own = next((r for r in rems if r["id"] == reminder_id), None)
        check("提醒进入个人提醒列表", own is not None and own.get("source") == "user" and own.get("course_id") is None)
        st, inbox, _ = request("GET", "/api/notifications?page_size=100", token=s1_t)
        check("提醒在窗口内生成站内通知",
              any(n["reminder_id"] == reminder_id for n in inbox["items"]))
        st, _, _ = request("POST", f"/api/hospital/records/{advice['id']}/reminder", token=s2_t, body={
            "due_at": iso(due),
        })
        check("不能拿别人的嘱托建提醒", st == 403, f"status={st}")
        condition = next(r for r in records if r["record_type"] == "condition")
        st, _, _ = request("POST", f"/api/hospital/records/{condition['id']}/reminder", token=s1_t, body={
            "due_at": iso(due),
        })
        check("非医嘱资料不能转提醒", st == 400, f"status={st}")

        st, grant, _ = request("POST", "/api/hospital/caregivers", token=s1_t, body={
            "caregiver_username": "s2024002", "relation": "家属",
        })
        check("患者授权照护者", st == 200 and grant.get("status") == "active", str(grant))
        grant_id = grant["id"]
        patient_id = grant["patient_user_id"]
        st, received, _ = request("GET", "/api/hospital/caregivers", token=s2_t)
        check("照护者能看到收到的授权",
              any(g["id"] == grant_id for g in received.get("received", [])), str(received))
        st, shared, _ = request("GET", f"/api/hospital/records?patient_id={patient_id}", token=s2_t)
        check("照护者可读患者资料", st == 200 and len(shared) == 3, str(len(shared)))
        st, auths_shared, _ = request("GET", f"/api/hospital/authorizations?patient_id={patient_id}", token=s2_t)
        check("照护者可看授权状态且标识脱敏",
              st == 200 and raw_ref not in json.dumps(auths_shared, ensure_ascii=False))
        st, _, _ = request("POST", f"/api/hospital/records/{advice['id']}/reminder", token=s2_t, body={
            "due_at": iso(due),
        })
        check("照护者不能替患者建提醒", st == 403)
        st, _, _ = request("POST", f"/api/hospital/authorizations/{auth_id}/sync", token=s2_t)
        check("照护者不能替患者同步", st == 404, f"status={st}")

        st, revoked_grant, _ = request("DELETE", f"/api/hospital/caregivers/{grant_id}", token=s1_t)
        check("患者可撤销照护授权", st == 200 and revoked_grant.get("status") == "revoked")
        st, _, _ = request("GET", f"/api/hospital/records?patient_id={patient_id}", token=s2_t)
        check("撤销后照护者不能再读", st == 403, f"status={st}")

        # HTTP 医院：正常同步、上游失败、缓存仍可读
        st, auth2, _ = request("POST", "/api/hospital/authorizations", token=s1_t, body={
            "partner_id": remote_id, "patient_ref": "REMOTE-P-001", "consent": True,
        })
        check("授权 HTTP 模式医院", st == 200 and auth2.get("status") == "active", str(auth2))
        st, sync2, _ = request("POST", f"/api/hospital/authorizations/{auth2['id']}/sync", token=s1_t)
        check("HTTP 医院同步成功", st == 200 and sync2.get("added") == 2, str(sync2))
        st, records_all, _ = request("GET", "/api/hospital/records", token=s1_t)
        check("两种医院资料合并展示", st == 200 and len(records_all) == 5, str(len(records_all)))

        FakeHospital.fail = True
        st, payload, _ = request("POST", f"/api/hospital/authorizations/{auth2['id']}/sync", token=s1_t)
        check("上游异常返回可理解错误", st == 502 and "医院接口" in str(payload), str(payload))
        st, records_after_fail, _ = request("GET", "/api/hospital/records", token=s1_t)
        check("上游异常不影响已缓存资料", st == 200 and len(records_after_fail) == 5)
        FakeHospital.fail = False

        st, revoked, _ = request("DELETE", f"/api/hospital/authorizations/{auth_id}", token=s1_t)
        check("用户可撤销医院授权", st == 200 and revoked.get("status") == "revoked")
        st, records_revoked, _ = request("GET", "/api/hospital/records", token=s1_t)
        check("撤销授权后不再返回该院资料",
              st == 200 and all(r["partner_id"] != demo_id for r in records_revoked), str(records_revoked))
        st, _, _ = request("GET", f"/api/hospital/records/{advice['id']}", token=s1_t)
        check("撤销授权后资料详情不可读", st == 403)
        st, _, _ = request("POST", f"/api/hospital/authorizations/{auth_id}/sync", token=s1_t)
        check("撤销授权后不能继续同步", st == 403, f"status={st}")

        st, reauth, _ = request("POST", "/api/hospital/authorizations", token=s1_t, body={
            "partner_id": demo_id, "patient_ref": "P2024001XYZ", "consent": True,
        })
        check("可重新授权", st == 200 and reauth.get("status") == "active")
        st, sync3, _ = request("POST", f"/api/hospital/authorizations/{reauth['id']}/sync", token=s1_t)
        check("重复同步不产生重复资料", st == 200 and sync3.get("added") == 0 and sync3.get("total") == 3, str(sync3))
        st, records_back, _ = request("GET", "/api/hospital/records", token=s1_t)
        check("重新授权后资料恢复", st == 200 and len(records_back) == 5)

        st, disabled, _ = request("PATCH", f"/api/hospital/admin/partners/{demo_id}", token=admin_t, body={
            "status": "disabled",
        })
        check("管理员可停用医院", st == 200 and disabled.get("status") == "disabled")
        st, partners_after, _ = request("GET", "/api/hospital/partners", token=s1_t)
        check("停用医院不再出现在可选列表", all(p["id"] != demo_id for p in partners_after))
        st, _, _ = request("POST", f"/api/hospital/authorizations/{reauth['id']}/sync", token=s1_t)
        check("停用医院不能继续同步", st == 400, f"status={st}")

        log_file.flush()
        log_text = LOG.read_text(encoding="utf-8", errors="replace")
        check("日志不出现患者标识", raw_ref not in log_text and "REMOTE-P-001" not in log_text)
        check("日志不出现医院 Token", REMOTE_TOKEN not in log_text)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
        fake.shutdown()

    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\n结果：{passed}/{len(checks)} 通过")
    if passed != len(checks):
        print("\n失败项：")
        for name, ok, detail in checks:
            if not ok:
                print(" -", name, detail)
        print(f"\n测试目录保留用于排障：{TEST_DIR}")
        sys.exit(1)
    shutil.rmtree(TEST_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
