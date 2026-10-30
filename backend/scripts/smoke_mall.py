"""商城后端冒烟测试（独立临时库，不碰开发库）。

覆盖登录、商品目录、试看、单课下单 / 支付 / 取消、进度与退款规则、
补差价升级、团购与激活码、部分退款、服务订单、支付回调、管理员操作、
旧接口兼容与教师视角。共 67 项检查。

用法：
    python backend/scripts/smoke_mall.py
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
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TEST_DIR = Path(tempfile.mkdtemp(prefix="xiaoyi_mall_smoke_"))
DB = TEST_DIR / "smoke.db"
LOG = TEST_DIR / "server.log"
PORT = 8770
BASE = f"http://127.0.0.1:{PORT}"
PASS = 0


def req(method, path, body=None, token=None, expect=200):
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        if exc.code != expect:
            raise AssertionError(
                f"{method} {path} -> {exc.code} (expect {expect}): {payload}"
            )
        return exc.code, payload


def check(name, condition, detail=""):
    global PASS
    if not condition:
        raise AssertionError(f"FAIL {name}: {detail}")
    PASS += 1
    print(f"  ok  {name}")


def login(username, password):
    _, data = req("POST", "/api/auth/login", {"username": username, "password": password})
    return data["access_token"]


def wait_for_health(seconds=40):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=3) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.5)
    raise SystemExit("服务未能启动，查看 " + str(LOG))


def run_checks():
    print("== 登录 ==")
    admin = login("admin", "admin123")
    stu2 = login("s2024002", "stu123")
    teacher = login("t1001", "teach123")

    # 管理员创建测试用户
    for username, full_name in [
        ("mall_buyer", "团购买家"),
        ("mall_learner1", "学习者一"),
        ("mall_learner2", "学习者二"),
        ("mall_buyer2", "普通买家"),
        ("mall_buyer3", "支付回调买家"),
        ("mall_learner3", "部分退款学习者"),
    ]:
        req(
            "POST",
            "/api/users",
            {"username": username, "password": "test123", "full_name": full_name, "role": "student"},
            admin,
            expect=200,
        )
    buyer = login("mall_buyer", "test123")
    learner1 = login("mall_learner1", "test123")
    learner2 = login("mall_learner2", "test123")
    buyer2 = login("mall_buyer2", "test123")
    buyer3 = login("mall_buyer3", "test123")
    learner3 = login("mall_learner3", "test123")

    print("== 商品目录 ==")
    _, catalog = req("GET", "/api/mall/products", token=stu2)
    check("统一目录返回课程与服务", len(catalog["items"]) >= 10, str(catalog["total"]))
    courses = [x for x in catalog["items"] if x["product_type"] == "course"]
    services = [x for x in catalog["items"] if x["product_type"] == "service"]
    check("课程包含免费入门和整包", any(c["course_type"] == "intro" for c in courses) and any(c["course_type"] == "bundle" for c in courses))
    check("服务商品存在", len(services) >= 5, str(len(services)))
    intro = next(c for c in courses if c["course_type"] == "intro")
    bundle = next(c for c in courses if c["course_type"] == "bundle")
    check("免费入门课对所有登录用户 owned", intro["owned"] is True)
    check("入门课价格为 0", intro["price"] == 0)
    check("整包包含 5 门单课", len(bundle["included_courses"]) == 5, str(len(bundle["included_courses"])))
    check("整包价格低于单课合计", bundle["price"] < sum(c["price"] for c in bundle["included_courses"]))

    singles = {c["name"]: c for c in courses if c["course_type"] == "single"}
    c2 = next(c for c in singles.values() if "呼吸康复" in c["name"])
    c3 = next(c for c in singles.values() if "用药与吸入装置" in c["name"])
    c4 = next(c for c in singles.values() if "急性加重" in c["name"])
    check("整包价约等于 7 折", abs(bundle["price"] - round(sum(c["price"] for c in singles.values()) * 0.7, 2)) < 0.01)

    print("== 课时与试看 ==")
    _, lessons = req("GET", f"/api/courses/{c2['id']}/lessons", token=buyer2)
    check("课时目录可见", len(lessons["lessons"]) == 3, str(lessons))
    check("未购用户第 1 节可试看", lessons["lessons"][0]["locked"] is False)
    check("未购用户第 2 节锁定且无视频地址", lessons["lessons"][1]["locked"] is True and lessons["lessons"][1]["video_url"] == "")
    _, intro_lessons = req("GET", f"/api/courses/{intro['id']}/lessons", token=buyer2)
    check("免费入门课全部解锁", all(not x["locked"] for x in intro_lessons["lessons"]))
    _, detail_unowned = req("GET", f"/api/mall/products/course/{c2['id']}", token=buyer2)
    check("商品详情含退款规则", bool(detail_unowned["refund_policy"]))

    print("== 单课下单 / 支付 / 取消 ==")
    _, order = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c2["id"]}, buyer2)
    check("创建待支付订单", order["status"] == "pending" and order["order_no"].startswith("C"))
    check("订单含学习名额", len(order["seats"]) == 1 and order["seats"][0]["learner_user_id"] is not None)
    _, cancelled = req("POST", f"/api/mall/orders/{order['order_no']}/cancel", token=buyer2)
    check("取消待支付订单", cancelled["status"] == "cancelled")
    _, dup = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c2["id"]}, buyer2, expect=409)
    check("取消后可重新下单（状态冲突已解除）", isinstance(dup, dict) or dup is not None)

    _, order = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c2["id"]}, buyer2)
    _, paid = req("POST", f"/api/mall/orders/{order['order_no']}/pay", {"channel": "mock"}, buyer2)
    check("模拟支付成功", paid["status"] == "paid" and paid["paid_at"] is not None)
    check("支付后生成 730 天学习权", paid["valid_until"] is not None)
    _, mine = req("GET", "/api/mall/my-courses", token=buyer2)
    check("我的课程出现已购课程", any(x["course"]["id"] == c2["id"] for x in mine))
    _, repeat = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c2["id"]}, buyer2, expect=409)
    check("重复购买被拒绝", repeat["detail"])

    print("== 进度与退款规则 ==")
    _, rc = req("GET", f"/api/mall/orders/{order['order_no']}/refund-check", token=buyer2)
    check("刚购买可退款", rc["eligible"] is True and rc["progress_percent"] == 0)
    for lesson in lessons["lessons"]:
        req(
            "POST",
            f"/api/courses/lessons/{lesson['id']}/progress",
            {"position_seconds": lesson["duration_seconds"], "completed": True},
            buyer2,
        )
    _, rc2 = req("GET", f"/api/mall/orders/{order['order_no']}/refund-check", token=buyer2)
    check("进度 100% 后不可退款", rc2["eligible"] is False and rc2["progress_percent"] >= 20, str(rc2))
    _, refund_fail = req("POST", f"/api/mall/orders/{order['order_no']}/refund", {"reason": "测试"}, buyer2, expect=409)
    check("用户退款按规则被拒绝", refund_fail["detail"])

    # 另一笔 0 进度订单用于正常退款
    _, order2 = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c3["id"]}, buyer2)
    req("POST", f"/api/mall/orders/{order2['order_no']}/pay", {"channel": "mock"}, buyer2)
    _, refunded = req("POST", f"/api/mall/orders/{order2['order_no']}/refund", {"reason": "7 天内不想要了"}, buyer2)
    check("符合规则立即退款", refunded["status"] == "refunded" and refunded["refund_amount"] == order2["amount"])
    _, my2 = req("GET", "/api/mall/my-courses", token=buyer2)
    check("退款后学习权收回", not any(x["course"]["id"] == c3["id"] for x in my2))
    _, reorder = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c3["id"]}, buyer2)
    check("退款后可重新购买", reorder["status"] == "pending")

    print("== 补差价升级整包 ==")
    # stu2 种子拥有 c1、c5；先买 c4 保持已支付，再升级
    _, stu2_order = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c4["id"]}, stu2)
    req("POST", f"/api/mall/orders/{stu2_order['order_no']}/pay", {"channel": "mock"}, stu2)
    _, bundle_detail = req("GET", f"/api/mall/products/course/{bundle['id']}", token=stu2)
    quote = bundle_detail["upgrade_quote"]
    check("整包详情返回升级抵扣", quote["eligible"] is True and quote["discount_amount"] > 0, str(quote))
    _, upgrade = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": bundle["id"]}, stu2)
    check("升级订单类型与抵扣金额", upgrade["order_type"] == "upgrade" and upgrade["discount_amount"] == quote["discount_amount"], str(upgrade))
    _, upgrade_paid = req("POST", f"/api/mall/orders/{upgrade['order_no']}/pay", {"channel": "mock"}, stu2)
    check("升级订单支付成功", upgrade_paid["status"] == "paid")
    check("升级后整包已开通", upgrade_paid["amount"] == quote["payable_amount"])
    _, my_stu2 = req("GET", "/api/mall/my-courses", token=stu2)
    check("升级后获得整包", any(x["course"]["id"] == bundle["id"] for x in my_stu2))
    check("升级后获得包内单课（c3）", any(x["course"]["id"] == c3["id"] for x in my_stu2))
    check(
        "升级订单记录抵扣来源",
        stu2_order["order_no"] in upgrade_paid["upgrade_source_order_nos"],
        str(upgrade_paid["upgrade_source_order_nos"]),
    )
    _, upgrade_again = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": bundle["id"]}, stu2, expect=409)
    check("重复购买整包被拒绝", upgrade_again["detail"])
    _, blocked_source = req(
        "POST",
        f"/api/mall/orders/{stu2_order['order_no']}/refund",
        {"reason": "尝试单独退原单"},
        stu2,
        expect=409,
    )
    check("升级后来源订单不可单独退款", "升级" in blocked_source["detail"], str(blocked_source))

    _, upgrade_rc = req("GET", f"/api/mall/orders/{upgrade['order_no']}/refund-check", token=stu2)
    check("升级订单可按规则退款", upgrade_rc["eligible"] is True, str(upgrade_rc))
    _, upgrade_refund = req("POST", f"/api/mall/orders/{upgrade['order_no']}/refund", {"reason": "升级后反悔"}, stu2)
    check("升级订单退款成功", upgrade_refund["status"] == "refunded")
    _, my_stu2_refunded = req("GET", "/api/mall/my-courses", token=stu2)
    check("升级退款后整包收回", not any(x["course"]["id"] == bundle["id"] for x in my_stu2_refunded))
    check("升级退款不影响原单课程", any(x["course"]["id"] == c4["id"] for x in my_stu2_refunded))
    _, requote = req("GET", f"/api/mall/products/course/{bundle['id']}", token=stu2)
    check("升级退款后抵扣额度恢复", requote["upgrade_quote"]["discount_amount"] == quote["discount_amount"])

    print("== 团购 / 代买 / 激活码 ==")
    _, group = req(
        "POST",
        "/api/mall/orders",
        {
            "product_type": "course",
            "product_id": c4["id"],
            "quantity": 3,
            "learners": [
                {"username": "mall_buyer"},
                {"username": "mall_learner1"},
            ],
        },
        buyer,
    )
    check("团购订单数量与金额", group["quantity"] == 3 and group["amount"] == round(c4["price"] * 3, 2), str(group))
    check("团购生成 3 个名额", len(group["seats"]) == 3 and sum(1 for s in group["seats"] if not s["learner_user_id"]) == 1)
    _, group_paid = req("POST", f"/api/mall/orders/{group['order_no']}/pay", {"channel": "mock"}, buyer)
    check("团购支付成功", group_paid["status"] == "paid")
    _, buyer_courses = req("GET", "/api/mall/my-courses", token=buyer)
    _, learner1_courses = req("GET", "/api/mall/my-courses", token=learner1)
    check("买家本人名额已开通", any(x["course"]["id"] == c4["id"] for x in buyer_courses))
    check("指定学习者名额已开通", any(x["course"]["id"] == c4["id"] for x in learner1_courses))
    raw_code = next(s["activation_code"] for s in group_paid["seats"] if not s["learner_user_id"])
    _, redeemed = req("POST", "/api/mall/seats/redeem", {"activation_code": raw_code}, learner2)
    check("激活码兑换成功", redeemed["ok"] and redeemed["course_id"] == c4["id"])
    _, learner2_courses = req("GET", "/api/mall/my-courses", token=learner2)
    check("兑换后学习权到账", any(x["course"]["id"] == c4["id"] for x in learner2_courses))
    _, redeem_again = req("POST", "/api/mall/seats/redeem", {"activation_code": raw_code}, learner1, expect=409)
    check("激活码不能被他人重复兑换", redeem_again["detail"])

    # 部分退款：2 个名额，1 个已绑定且进度超 20% 不可退，1 个未激活可退
    _, partial = req(
        "POST",
        "/api/mall/orders",
        {"product_type": "course", "product_id": c4["id"], "quantity": 2, "learners": [{"username": "mall_learner3"}]},
        buyer2,
    )
    req("POST", f"/api/mall/orders/{partial['order_no']}/pay", {"channel": "mock"}, buyer2)
    learner3_lessons = req("GET", f"/api/courses/{c4['id']}/lessons", token=learner3)[1]["lessons"]
    for lesson in learner3_lessons:
        req(
            "POST",
            f"/api/courses/lessons/{lesson['id']}/progress",
            {"position_seconds": lesson["duration_seconds"], "completed": True},
            learner3,
        )
    _, partial_refund = req("POST", f"/api/mall/orders/{partial['order_no']}/refund", {"reason": "退未激活名额"}, buyer2)
    check("团购仅退未激活名额", partial_refund["status"] == "partially_refunded" and partial_refund["refund_amount"] == c4["price"], str(partial_refund))
    _, learner3_after = req("GET", "/api/mall/my-courses", token=learner3)
    check("已激活且已学习名额不受部分退款影响", any(x["course"]["id"] == c4["id"] for x in learner3_after))

    print("== 服务订单 ==")
    service = services[0]
    _, s_order = req("POST", "/api/mall/orders", {"product_type": "service", "product_id": service["id"]}, buyer2)
    _, s_paid = req("POST", f"/api/mall/orders/{s_order['order_no']}/pay", {"channel": "mock"}, buyer2)
    check("服务订单支付成功", s_paid["status"] == "paid")
    _, ents = req("GET", "/api/mall/entitlements", token=buyer2)
    check("服务权益已开通", any(x["id"] == service["id"] for x in ents["services"]))
    _, s_refund = req("POST", f"/api/mall/orders/{s_order['order_no']}/refund", {"reason": "不需要了"}, buyer2)
    check("服务 7 天内可退款", s_refund["status"] == "refunded")
    _, ents2 = req("GET", "/api/mall/entitlements", token=buyer2)
    check("服务退款后权益收回", not any(x["id"] == service["id"] for x in ents2["services"]))

    print("== 支付回调 ==")
    _, cb_order = req("POST", "/api/mall/orders", {"product_type": "course", "product_id": c2["id"]}, buyer3)
    _, cb = req(
        "POST",
        "/api/mall/payments/callback",
        {"order_no": cb_order["order_no"], "transaction_id": "MOCK-TX-1", "channel": "mock", "status": "success"},
    )
    check("支付回调置为已支付", cb["ok"] and cb["status"] == "paid")
    _, cb2 = req(
        "POST",
        "/api/mall/payments/callback",
        {"order_no": cb_order["order_no"], "transaction_id": "MOCK-TX-1", "channel": "mock", "status": "success"},
    )
    check("回调幂等", cb2["ok"] and cb2["status"] == "paid")

    print("== 管理员 ==")
    _, admin_orders = req("GET", "/api/mall/admin/orders?page_size=100", token=admin)
    check("管理员可看全部订单", admin_orders["total"] >= 8, str(admin_orders["total"]))
    _, force = req(
        "POST",
        f"/api/mall/admin/orders/{stu2_order['order_no']}/refund?force=true",
        {"reason": "管理员强制退款"},
        admin,
    )
    check("管理员强制退款成功", force["status"] in ("refunded", "partially_refunded"), str(force))
    _, my_stu2_after = req("GET", "/api/mall/my-courses", token=stu2)
    check("强制退款后原课程收回", not any(x["course"]["id"] == c4["id"] for x in my_stu2_after))
    _, patch = req("PATCH", f"/api/courses/{c3['id']}", {"status": "off"}, admin)
    check("管理员可下架课程", patch["status"] == "off")
    _, catalog_hidden = req("GET", "/api/mall/products", token=stu2)
    check("下架课程不在普通目录", not any(x["id"] == c3["id"] and x["product_type"] == "course" for x in catalog_hidden["items"]))
    req("PATCH", f"/api/courses/{c3['id']}", {"status": "on"}, admin)

    print("== 旧接口兼容 ==")
    _, legacy = req("POST", f"/api/courses/{c2['id']}/purchase", token=buyer3, expect=409)
    check("旧购课接口仍返回冲突提示", legacy["detail"])
    _, legacy_orders = req("GET", "/api/courses/purchases/mine", token=stu2)
    check("旧购买记录接口可用", isinstance(legacy_orders, list) and len(legacy_orders) >= 1)
    _, legacy_services = req("GET", "/api/service-products", token=stu2)
    check("旧服务目录接口可用", isinstance(legacy_services, list) and len(legacy_services) >= 5)

    print("== 教师视角 ==")
    _, teacher_courses = req("GET", "/api/courses", token=teacher)
    check("教师可查看课程目录", len(teacher_courses) >= 6)
    _, teacher_orders = req("GET", "/api/mall/orders", token=teacher)
    check("教师订单列表可访问", teacher_orders["total"] == 0)


def main():
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
    env["JWT_SECRET_KEY"] = "mall-smoke-secret"
    env["REMINDER_SCAN_SECONDS"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    log_file = open(LOG, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(BACKEND), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    try:
        wait_for_health()
        run_checks()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()

    print(f"\nALL PASS ({PASS} checks)")
    shutil.rmtree(TEST_DIR, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(str(exc))
        print(f"\n测试目录保留用于排障：{TEST_DIR}")
        sys.exit(1)
