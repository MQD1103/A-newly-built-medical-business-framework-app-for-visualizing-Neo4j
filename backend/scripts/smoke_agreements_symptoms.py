"""用户协议 / 隐私政策 + 症状日记 冒烟测试。

在临时库上启动真实后端，验证：
症状日记的增改查、同日覆盖、未来日期拒绝、加重提示；
协议目录与全文、同意记录留痕、幂等、版本校验、未登录拒绝。

不会读写 backend/edu.db。用法：
    python backend/scripts/smoke_agreements_symptoms.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TEST_DIR = Path(tempfile.mkdtemp(prefix="xiaoyi_agree_smoke_"))
DB = TEST_DIR / "smoke.db"
LOG = TEST_DIR / "server.log"
PORT = 8772
BASE = f"http://127.0.0.1:{PORT}"

checks = []


def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail and not cond else ""))


def request(method, path, token=None, body=None, timeout=30):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # 本机回环请求不走系统代理，避免代理软件劫持 127.0.0.1
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def wait_ready(deadline=60):
    for _ in range(deadline * 4):
        try:
            status, _body = request("GET", "/api/health", timeout=3)
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def main() -> int:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{DB}"
    env["JWT_SECRET_KEY"] = "smoke-agreements-secret"
    log_write = LOG.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=log_write,
        stderr=subprocess.STDOUT,
    )
    try:
        if not wait_ready():
            print("后端未能就绪，日志：")
            print(LOG.read_text(encoding="utf-8"))
            return 1

        # ---------- 症状日记 ----------
        status, body = request("POST", "/api/auth/login", body={"username": "s2024001", "password": "stu123"})
        check("登录成功", status == 200 and body and body.get("access_token"))
        token = body["access_token"]

        status, body = request("GET", "/api/symptoms", token=token)
        check("症状日记初始为空", status == 200 and body["items"] == [] and body["warning"] is False)

        today = date.today().isoformat()
        status, body = request(
            "POST",
            "/api/symptoms",
            token=token,
            body={"cough": 3, "dyspnea": 0, "sputum": 0, "note": "夜间咳嗽"},
        )
        check("记录症状成功", status == 200 and body["total"] == 3)
        check("重度单项触发加重提示", body["warning"] is True and "咳嗽" in body["warning_text"])
        entry_id = body["id"]

        status, body = request("GET", "/api/symptoms", token=token)
        check("列表返回一条", status == 200 and len(body["items"]) == 1)

        # 同日再提交 = 覆盖更新
        status, body = request(
            "POST", "/api/symptoms", token=token, body={"cough": 1, "dyspnea": 1, "sputum": 0}
        )
        check("同日提交按更新处理", status == 200 and body["id"] == entry_id and body["total"] == 2)
        check("降级后不再提示加重", body["warning"] is False)

        future = (date.today() + timedelta(days=1)).isoformat()
        status, _body = request("POST", "/api/symptoms", token=token, body={"record_date": future})
        check("拒绝未来日期", status == 400)

        status, _body = request("POST", "/api/symptoms", body={"cough": 1})
        check("未登录不能写症状", status == 401)

        # ---------- 用户协议 / 隐私政策 ----------
        status, body = request("GET", "/api/agreements")
        check("协议目录公开可访问", status == 200 and len(body) == 2)
        check("目录不携带全文", all(item["content"] is None for item in body))

        status, body = request("GET", "/api/agreements/user_agreement")
        check("用户协议全文可读（免登录）", status == 200 and "小医用户协议" in body["content"])
        status, body = request("GET", "/api/agreements/privacy_policy")
        check("隐私政策全文可读（免登录）", status == 200 and "小医隐私政策" in body["content"])
        status, _body = request("GET", "/api/agreements/not_exist")
        check("未知协议返回 404", status == 404)

        # ---------- 同意记录 ----------
        status, body = request("GET", "/api/consents/me", token=token)
        check("新用户有待同意协议", status == 200 and len(body["pending"]) == 2 and body["consents"] == [])
        pending_before = sorted(body["pending"])

        status, body = request("POST", "/api/consent", token=token, body={"agreement_type": pending_before[0]})
        check("同意一条成功", status == 200 and body["agreement_type"] == pending_before[0])
        first_accepted_at = body["accepted_at"]

        # 幂等：重复同意同一版本返回同一条记录
        status, body2 = request("POST", "/api/consent", token=token, body={"agreement_type": pending_before[0]})
        check("重复同意保持幂等", status == 200 and body2["accepted_at"] == first_accepted_at)

        status, body = request("GET", "/api/consents/me", token=token)
        check("同意后 pending 只剩一条", len(body["pending"]) == 1 and len(body["consents"]) == 1)
        check("同意记录含版本号", body["consents"][0]["version"] == "1.0.0")

        status, _body = request(
            "POST", "/api/consent", token=token, body={"agreement_type": "user_agreement", "version": "9.9.9"}
        )
        check("未知版本返回 400", status == 400)

        status, _body = request("POST", "/api/consent", body={"agreement_type": "user_agreement"})
        check("未登录不能写同意记录", status == 401)

        status, body = request("GET", "/api/consents/me")
        check("未登录不能查同意记录", status == 401)

        print()
        passed = sum(1 for _, ok, _ in checks if ok)
        print(f"通过 {passed}/{len(checks)}")
        return 0 if passed == len(checks) else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_write.close()
        shutil.rmtree(TEST_DIR, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
