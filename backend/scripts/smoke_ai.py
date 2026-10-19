"""AI 用药动作检测冒烟测试。

在临时库上启动真实后端与本地假检测服务，验证：
鉴权、图片类型 / 大小校验、限流、结果摘要落库、仅本人可见、
检测服务异常与格式异常、历史清理字段、日志不含影像与 Token。
同时直接调用一次内置演示模式。

不会读写 backend/edu.db。用法：
    python backend/scripts/smoke_ai.py
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
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TEST_DIR = Path(tempfile.mkdtemp(prefix="xiaoyi_ai_smoke_"))
DB = TEST_DIR / "smoke.db"
LOG = TEST_DIR / "server.log"
PORT = 8769
BASE = f"http://127.0.0.1:{PORT}"
DETECTOR_TOKEN = "test-detector-token"
IMAGE_MARKER = b"XIAOYI_TEST_IMAGE_MARKER"

PNG = b"\x89PNG\r\n\x1a\n" + IMAGE_MARKER + b"\x00" * 64
checks = []


def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail and not cond else ""))


def request(method, path, token=None, body=None, headers=None, timeout=30, raw_body=None):
    data = raw_body
    all_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        all_headers["Content-Type"] = "application/json"
    if token:
        all_headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=all_headers, method=method)
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


def upload(token, data=PNG, content_type="image/png", filename="photo.png", lesson_id=None):
    boundary = "----xiaoyiAITestBoundary"
    chunks = []
    if lesson_id is not None:
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="lesson_id"\r\n\r\n'
            f"{lesson_id}\r\n".encode("utf-8")
        )
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode("utf-8")
        + data
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    return request(
        "POST",
        "/api/ai/medication-checks",
        token=token,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        timeout=60,
        raw_body=body,
    )


class FakeDetector(BaseHTTPRequestHandler):
    mode = "ok"  # ok / fail / bad

    def do_POST(self):  # noqa: N802
        if self.headers.get("Authorization") != f"Bearer {DETECTOR_TOKEN}":
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if FakeDetector.mode == "fail":
            self.send_error(500)
            return
        if FakeDetector.mode == "bad":
            raw = b"not-a-json"
        else:
            raw = json.dumps(
                {
                    "steps": [
                        {"name": "核对药名", "done": True},
                        {"name": "完成本次用药动作", "done": False},
                    ],
                    "needs_retry": True,
                    "message": "请按提示重做未完成步骤。",
                },
                ensure_ascii=False,
            ).encode("utf-8")
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


def demo_mode_check():
    sys.path.insert(0, str(BACKEND))
    from app import ai_service

    old = os.environ.pop("AI_DETECTOR_URL", None)
    try:
        steps, needs_retry, message, provider = ai_service.detect(PNG, "image/png")
    finally:
        if old is not None:
            os.environ["AI_DETECTOR_URL"] = old
    check("未配置检测服务时使用演示模式", provider == "demo")
    check("演示模式返回步骤摘要而非药效结论", len(steps) >= 1 and all("name" in s for s in steps))
    check("演示模式明确标注仅供联调", "演示" in message)
    check("结果附带合规声明", "不构成诊断" in ai_service.DISCLAIMER)


def main():
    demo_mode_check()

    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeDetector)
    detector_url = f"http://127.0.0.1:{fake.server_address[1]}/detect"
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
    env["JWT_SECRET_KEY"] = "ai-smoke-secret"
    env["REMINDER_SCAN_SECONDS"] = "60"
    env["AI_DETECTOR_URL"] = detector_url
    env["AI_DETECTOR_TOKEN"] = DETECTOR_TOKEN
    env["AI_DETECTOR_TIMEOUT_SECONDS"] = "3"
    env["AI_IMAGE_MAX_MB"] = "1"
    env["AI_RATE_LIMIT"] = "8"
    env["AI_RATE_WINDOW_SECONDS"] = "60"
    env["AI_RESULT_RETENTION_DAYS"] = "30"
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
        check("启动后存在检测记录表", "medication_checks" in tables)

        tokens = {}
        for name, username, password in (
            ("s1", "s2024001", "stu123"),
            ("s2", "s2024002", "stu123"),
        ):
            st, payload, _ = login(username, password)
            check(f"{name} 登录", st == 200 and payload.get("access_token"))
            tokens[name] = payload["access_token"]
        s1_t, s2_t = tokens["s1"], tokens["s2"]

        st, lessons, _ = request("GET", "/api/courses/1/lessons", token=s1_t)
        lesson_id = lessons["lessons"][0]["id"] if st == 200 and lessons.get("lessons") else None
        check("可取得课时用于关联", lesson_id is not None)

        st, _, _ = request("POST", "/api/ai/medication-checks", body={})
        check("检测接口需要登录", st in (401, 403, 422), f"status={st}")

        st, result, _ = upload(s1_t, lesson_id=lesson_id)
        check("正常图片检测成功", st == 200 and result.get("status") == "completed", str(result))
        check("返回步骤摘要", [s["name"] for s in result.get("steps", [])] == ["核对药名", "完成本次用药动作"], str(result))
        check("返回是否需要重做", result.get("needs_retry") is True)
        check("关联课时被记录", result.get("lesson_id") == lesson_id)
        check("结果带合规声明", "不构成诊断" in (result.get("disclaimer") or ""))
        check("响应不包含图片内容字段",
              not any(k in ("image", "image_data", "image_base64") for k in result)
              and IMAGE_MARKER.decode("ascii") not in json.dumps(result, ensure_ascii=False))
        first_id = result["id"]

        st, invalid_type, _ = upload(s1_t, data=b"hello", content_type="text/plain", filename="a.txt")
        check("拒绝非图片类型", st == 400, f"status={st}")
        st, mismatch, _ = upload(s1_t, data=b"not-a-real-png", content_type="image/png")
        check("拒绝伪造图片类型", st == 400, f"status={st}")
        st, empty, _ = upload(s1_t, data=b"", content_type="image/png")
        check("拒绝空图片", st == 400, f"status={st}")

        FakeDetector.mode = "fail"
        st, failed, _ = upload(s1_t)
        check("检测服务异常返回可理解错误", st == 502 and "检测服务" in str(failed), str(failed))
        FakeDetector.mode = "bad"
        st, bad, _ = upload(s1_t)
        check("检测服务返回格式异常时给出提示", st == 502 and "格式异常" in str(bad), str(bad))
        FakeDetector.mode = "ok"

        st, too_big, _ = upload(s1_t, data=PNG + b"\x00" * (1024 * 1024))
        check("超过大小限制返回 413", st == 413, f"status={st}")
        st, no_lesson, _ = upload(s1_t, lesson_id=999999)
        check("无效课时被拒绝", st == 404, f"status={st}")

        st, history, _ = request("GET", "/api/ai/medication-checks?page_size=100", token=s1_t)
        check("历史记录可查询", st == 200 and history.get("total", 0) >= 3, str(history.get("total")))
        check("历史记录只含摘要状态", all("status" in item for item in history.get("items", [])))
        check("历史记录带保留天数", history.get("retention_days") == 30)
        failed_rows = [i for i in history["items"] if i["status"] == "failed"]
        check("失败记录保留脱敏摘要", len(failed_rows) >= 2 and all(i["steps"] == [] for i in failed_rows))
        check("失败记录提示重试", all(i["needs_retry"] for i in failed_rows))

        con = sqlite3.connect(DB)
        cols = [r[1] for r in con.execute("pragma table_info(medication_checks)")]
        rows = con.execute("select steps_json, image_size, message from medication_checks").fetchall()
        con.close()
        check("数据表没有任何图片列", not any("image_data" in c or c == "image" for c in cols))
        check("只保存图片体积与类型", "image_size" in cols and "image_type" in cols)
        check("数据库不保存原始影像", all(IMAGE_MARKER not in str(r).encode("utf-8", "ignore") for r in rows))

        st, detail, _ = request("GET", f"/api/ai/medication-checks/{first_id}", token=s1_t)
        check("本人可查看单条记录", st == 200 and detail.get("id") == first_id)
        st, _, _ = request("GET", f"/api/ai/medication-checks/{first_id}", token=s2_t)
        check("他人不能查看记录", st == 404, f"status={st}")
        st, other_list, _ = request("GET", "/api/ai/medication-checks", token=s2_t)
        check("他人历史记录为空", st == 200 and other_list.get("total") == 0, str(other_list))
        st, _, _ = request("DELETE", f"/api/ai/medication-checks/{first_id}", token=s2_t)
        check("他人不能删除记录", st == 404, f"status={st}")

        # 限流：第 9 次触发 429（窗口内每人 8 次）
        statuses = []
        retry_header = None
        for _ in range(9):
            st, payload, headers = upload(s2_t)
            statuses.append(st)
            if st == 429:
                retry_header = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
        check("超过检测频率限制返回 429", statuses[:8] == [200] * 8 and statuses[8] == 429, str(statuses))
        check("429 返回 Retry-After", bool(retry_header and int(retry_header) > 0), str(retry_header))

        st, deleted, _ = request("DELETE", f"/api/ai/medication-checks/{first_id}", token=s1_t)
        check("本人可删除检测记录", st == 200 and deleted.get("ok") is True)
        st, _, _ = request("GET", f"/api/ai/medication-checks/{first_id}", token=s1_t)
        check("删除后记录不可见", st == 404)

        log_file.flush()
        log_text = LOG.read_text(encoding="utf-8", errors="replace")
        check("日志不出现检测服务 Token", DETECTOR_TOKEN not in log_text)
        check("日志不出现图片内容", IMAGE_MARKER.decode("ascii") not in log_text)
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
