# 商城后端说明（课程 / 服务 / 订单 / 退款 / 团购）

> 适用代码：`backend/app/mall_service.py`、`backend/app/routers/mall.py`、
> `backend/app/routers/courses.py`、`backend/app/routers/service_products.py`、
> `backend/app/routers/admin.py`。
> 在线接口文档：启动后端后访问 `http://127.0.0.1:8000/docs`（FastAPI 自动生成）。

## 1. 商品模型

| 类型 | `course_type` / 来源 | 说明 |
| --- | --- | --- |
| 免费入门课 | `intro` | 价格为 0，所有登录用户自动可学，不可下单 |
| 单课 | `single` | 单独售卖，购买后获得 2 年学习权 |
| 系统课整包 | `bundle` | 通过 `course_bundle_items` 关联多门单课，购买后自动获得包内单课访问权 |
| 健康服务 | `service_products` | 按服务有效期开通，一次只能买 1 份 |

种子数据（`seed.py::ensure_mall_catalog`）在旧库上补齐：

- 5 门 COPD 单课（保留原有 ¥2.99 演示价）；
- 1 门免费入门课（2 节，全部可试看）；
- 1 个系统课整包（价格为单课合计的 70%，`valid_days=730`，包含 5 门单课）；
- 每门付费课 3 节，第 1 节为试看，其余课时购买后解锁。

价格、有效期、上架状态、排序均由后台 `PATCH /api/courses/{id}`、
`PATCH /api/service-products/{id}` 维护。

### 1.1 本地演示视频

课时默认没有视频地址。需要在本机看播放效果时，执行：

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe backend\scripts\generate_demo_videos.py
```

- 每节课生成 10 秒、1280×720 的 H.264 MP4 和 JPG 封面，放在
  `backend/uploads/courses/demo/`；
- 只给 `video_url` 为空的课时补地址，不覆盖管理员填写的真实视频；
- 视频文件已在 `.gitignore` 中忽略，同事拉代码后重新执行脚本即可；
- 启动时 `seed.py::attach_demo_lesson_videos` 会在文件存在时自动补地址；
- 播放结束或点击「标记本节已学完」会调用课时进度接口，计入退款规则所需进度。

可选 `--source <本地片源> --seconds 10 --force` 使用自己的视频素材（需先确认版权/授权），
脚本会裁成 1280×720、去音轨后写入同一目录。当前本机演示片源为开源动画 **Sintel**
（© Blender Foundation，CC-BY 3.0，`https://media.w3.org/2010/05/sintel/trailer.mp4`）
中裁剪的 10 秒片段，仅用于本地界面预览，不进入仓库。

## 2. 学习权规则

- 学习权落在 `enrollments`（课程）与 `service_entitlements`（服务）。
- `enrollments.expires_at` 为空表示永久；购买产生的记录带到期时间（默认购买日 + 730 天）。
- 整包不复制包内单课的 `enrollments`，访问权通过 `course_bundle_items` 实时推导，
  因此整包退款只删除整包自身的学习权，不会误删用户单独购买的单课。
- 免费入门课、管理员、授课教师按角色直接放行，不写下单记录。
- 已购课程即使下架，仍出现在「我的课程」并可继续学习。
- 试看规则：`is_trial=true` 或整包/单课已拥有时，接口才返回 `video_url`；
  未购买的付费课时返回 `locked=true` 且 `video_url=""`。

## 3. 订单状态机

```
pending ──支付成功──> paid ──部分退款──> partially_refunded
   │                    │
   │                    └──全额退款──> refunded
   ├──用户取消──> cancelled
   └──超时(15 分钟)──> expired
```

- 待支付订单 TTL 为 15 分钟，查询订单/目录时惰性过期。
- 支付接口幂等：已支付订单重复调用不会重复开通。
- 金额为 0 的订单（如补差价后应付 0 元）创建后自动完成支付。
- 订单号：课程 `C` 前缀、服务 `S` 前缀；历史订单迁移时回填 `C-OLD-{id}` / `S-OLD-{id}`。

## 4. 退款规则

退款政策与需求文档 2.11 对齐：

- 购买后 **7 天内**，且**付费课时学习进度低于 20%**，支持全额退款；
- 超过 7 天或进度达到 20% 及以上，不再退款；
- 免费课与试看不涉及退款；
- 团购订单：**未激活名额始终可退**；已激活到个人账号的名额按上面的个人规则判断。
  因此团购可能整单退、部分退（`partially_refunded`）；
- 管理员可使用 `force=true` 强制退款，不受时间/进度限制；
- `GET /api/mall/orders/{order_no}/refund-check` 返回是否可退、可退金额、窗口截止时间、
  进度百分比与原因，前端应以此为准，不要自行计算；
- 退款成功后按 `order_id` 撤销对应学习权；整包订单退款会恢复被抵扣的旧单，
  允许用户再次补差价升级；
- 默认退款即时完成（演示支付）。设置 `MALL_AUTO_REFUND=0` 后，
  用户申请退款会进入 `refund_pending`，由管理员处理。

进度统计口径：`paid_total/paid_completed` 只统计非试看课时；
退款校验按每个名额对应的学习者计算，取已激活名额中的最高进度展示。

## 5. 补差价升级

- 用户已购买整包内若干单课时，购买整包可抵扣这些单课的实付金额；
  抵扣上限为整包价格，应付金额不小于 0。
- `GET /api/mall/products/course/{bundle_id}` 返回 `upgrade_quote`：
  `eligible / discount_amount / payable_amount / source_order_nos / source_course_names / message`。
- 下单时自动重新计算抵扣并写入 `discount_amount`、`order_type="upgrade"`、
  `upgrade_from_order_id`；支付成功后把来源订单标记为 `upgraded_to_order_id`。
- 整包订单全额退款后，来源订单的标记会恢复，抵扣额度重新可用。
- 已用于抵扣的来源订单不能单独退款（需先退整包），避免“退掉单课却保留升级优惠”；
  管理员强制退款不受此限制。
- 团购订单只有买家本人已激活的名额可计入抵扣（按单个名额计价），
  代买给他人的名额不产生升级额度。

## 6. 团购 / 机构代买

- 下单时 `quantity` 表示名额数（1–200）；`learners` 可指定已有用户
  （`user_id` 或 `username`），也可只填 `name/phone` 由系统生成激活码。
- 支付成功后：已指定的学习者立即开通；未指定名额生成 12 位激活码，
  学习者登录后调用 `POST /api/mall/seats/redeem` 绑定并开通。
- 激活码只能被一个账号兑换；重复兑换同一账号幂等，他人兑换返回 409。
- 部分退款只退可退名额，已开通且仍在学习的名额保留。

## 7. 接口清单

所有接口前缀 `/api`，除支付回调外均需 `Authorization: Bearer <token>`。

### 7.1 商品与权益

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/mall/products` | 登录 | 统一商品目录；参数 `product_type=all/course/service`、`category`、`q`、`include_off`（仅管理员） |
| GET | `/mall/products/{product_type}/{product_id}` | 登录 | 商品详情：课时、退款政策、整包升级报价 |
| GET | `/mall/summary` | 登录 | 商城概览：商品数、已购数、待支付/已支付订单数 |
| GET | `/mall/refund-policy` | 登录 | 退款政策常量与开关 |
| GET | `/mall/my-courses` | 登录 | 我的课程（含整包推导、到期时间、来源、进度） |
| GET | `/mall/entitlements` | 登录 | 我的课程 + 服务权益 |
| GET | `/courses/{id}/lessons` | 登录 | 课时目录（试看/锁定、视频地址） |
| GET | `/courses/{id}/progress` | 登录 | 课程进度（总进度 + 付费课时进度） |
| POST | `/courses/lessons/{lesson_id}/progress` | 登录 | 上报续播位置/完播：`position_seconds`、`completed` |
| POST | `/courses/{id}/lessons` | 管理员 | 新增课时 |
| PATCH/DELETE | `/courses/lessons/{lesson_id}` | 管理员 | 修改/删除课时 |
| GET/PUT | `/courses/{id}/bundle-items` | 管理员 | 查看/设置整包包含的单课 |

### 7.2 订单与支付

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/mall/orders` | 登录 | 创建订单：`product_type`、`product_id`、`quantity`、`learners`、`channel`、`remark` |
| POST | `/mall/orders/{order_no}/pay` | 本人 | 演示支付：`channel`、`transaction_id` |
| POST | `/mall/orders/{order_no}/cancel` | 本人 | 取消待支付订单 |
| GET | `/mall/orders`、`/mall/orders/mine` | 登录 | 我的订单；参数 `status`、`product_type`、`page`、`page_size` |
| GET | `/mall/orders/{order_no}` | 本人/管理员 | 订单详情 |
| GET | `/mall/orders/{order_no}/refund-check` | 本人/管理员 | 退款资格与可退金额 |
| POST | `/mall/orders/{order_no}/refund` | 本人 | 申请/执行退款：`reason` |
| POST | `/mall/seats/redeem` | 登录 | 激活码兑换：`activation_code` |
| POST | `/mall/payments/callback` | 渠道 | 支付回调：`order_no`、`transaction_id`、`channel`、`status=success/failed` |
| GET | `/mall/admin/orders` | 管理员 | 全部订单；可按 `status`、`product_type`、`buyer_id` 过滤 |
| POST | `/mall/admin/orders/{order_no}/refund?force=true` | 管理员 | 强制退款 |

### 7.3 兼容旧前端的接口

以下接口保留原有请求/响应形状，内部改走新订单模型：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/courses` | 在售课程（管理员看全部） |
| POST | `/courses/{id}/purchase` | 创建并立即支付课程订单 |
| GET | `/courses/purchases/mine` | 我的课程购买记录 |
| GET | `/service-products` | 服务目录 |
| POST | `/service-products/{id}/purchase` | 创建并立即支付服务订单 |
| GET | `/service-products/purchases/mine` | 我的服务购买记录 |
| POST | `/admin/users/{user_id}/courses` | 管理员代开通（写 ¥0 订单，永久有效） |
| DELETE | `/admin/users/{user_id}/courses/{course_id}` | 取消单独开通；若整包仍包含该课会提示 |
| POST/DELETE | `/admin/users/{user_id}/services[/{id}]` | 管理员代开通/取消服务 |

## 8. 错误码约定

| HTTP | 场景 |
| --- | --- |
| 400 | 参数不合法（如服务购买数量不为 1、激活码格式错误） |
| 401 | 未登录或 token 过期 |
| 403 | 无权查看/操作他人订单、课时未购买 |
| 404 | 商品/订单/课时/激活码不存在 |
| 409 | 已拥有该课程、重复购买、订单状态不允许、退款规则不满足、激活码已被占用 |

错误体统一为 `{"detail": "可直接展示给用户的中文说明"}`。

## 9. 数据库与迁移

新增表：

- `course_bundle_items`：整包与单课的关联（唯一约束 `bundle_id + course_id`）；
- `lessons`：课时；
- `lesson_progress`：学习进度（唯一约束 `user_id + lesson_id`）；
- `course_order_seats`：团购名额（唯一约束 `activation_code`）。

`backend/app/schema_migrate.py::ensure_schema()` 在应用启动时执行：

1. 对旧表逐列 `ALTER TABLE ADD COLUMN`（SQLite 安全）；
2. 回填默认值（`course_type='single'`、`enrollments.source='seed'`、
   历史订单号/单价/实付/支付时间等）；
3. 回填完成后再建唯一索引，避免历史空值冲突；
4. `seed_if_empty()` 补齐入门课、整包、课时与服务元数据，重复执行幂等。

已用旧库副本验证：用户、选课、购买记录数量不丢失；课程由 5 门扩展为 7 门；
历史订单号成功回填；二次启动不重复插入。

## 10. 配置项

| 环境变量 | 默认 | 作用 |
| --- | --- | --- |
| `MALL_AUTO_REFUND` | `1` | `0` 时用户退款转为 `refund_pending`，等待管理员处理 |
| `MALL_PAYMENT_CALLBACK_TOKEN` | 空 | 非空时，支付回调必须携带 `X-Payment-Token` 请求头 |

演示支付不接触真实资金。接入真实支付前必须在回调中补充渠道签名校验与金额核对；
密钥、Token 只放本机环境变量，不进入 Git。

## 11. 安全与合规

- JWT 鉴权；订单、退款、学习权均按当前登录用户校验，管理员接口单独鉴权。
- 订单/激活码不包含患者信息；接口与日志不输出病历、证件号等敏感内容。
- 支付回调仅暴露订单号与交易号；生产环境需增加签名、时间戳与重放防护。
- `edu.db`、上传文件、密钥均不在版本库中。

## 12. 测试记录

- 冒烟测试：`backend/scripts/smoke_mall.py` 使用独立临时库与真实后端，
  覆盖目录/试看/下单/支付/取消/重复购买/进度限制/退款/升级/整包退款恢复/
  团购/激活码/部分退款/服务订单/支付回调幂等/管理员强制退款与下架/
  旧接口兼容/教师视角，共 **67 项全部通过**。
- 迁移测试：复制现有 `backend/edu.db` 后执行启动迁移与种子，数据数量、列、索引、
  订单号回填、二次启动幂等均通过。

---

## 技术文档（按需求 5.3 四项）

- **操作人**：Claude Code（AI 开发助手；提交时请按团队要求替换为实际提交人姓名）
- **更改什么**：
  - 新增 `backend/app/mall_service.py`、`backend/app/routers/mall.py`；
  - 扩展 `models.py`、`schemas.py`、`schema_migrate.py`、`seed.py`；
  - 重写 `routers/courses.py`、`routers/service_products.py` 的售课/权益逻辑，
    并新增课时进度上报接口；
  - 调整 `routers/admin.py` 的代开通/取消逻辑与 `main.py` 路由注册；
  - 新增本文档 `docs/mall-backend.md`，更新 README 功能说明。
- **作用是什么**：完成后端商城主流程——免费入门/单课/整包售卖、2 年学习权、
  首节试看、课时进度、订单状态机、演示支付与回调、7 天且进度低于 20% 的退款、
  单课补差价升级整包、机构团购与激活码、服务商品订单，并兼容旧前端接口；
  提供可执行的数据库迁移与种子数据。
- **在什么时候**：2026-10-19 22:10

## 技术文档（商城演示视频补充）

- **操作人**：Claude Code（AI 开发助手；提交时请按团队要求替换为实际提交人姓名）
- **更改什么**：
  - 新增 `backend/scripts/generate_demo_videos.py`、`backend/requirements-dev.txt`；
  - `seed.py` 新增 `attach_demo_lesson_videos`，启动时只补空视频地址；
  - `frontend/src/pages/Courses.tsx` 新增课时列表、视频播放器、封面与进度上报；
  - `frontend/src/types.ts`、`styles.css` 增加课时类型与样式；
  - `.gitignore` 忽略本地生成的演示视频目录；
  - 更新本文件与 `README.md`。
- **作用是什么**：给商城课时补上可直接播放的短演示视频，打通「课程详情 → 课时列表 →
  播放 → 完播计入进度」的前端效果；视频由脚本本地生成或从开源片源（Sintel，CC-BY 3.0）
  裁剪、不入库、不进仓库，仅补空地址，不覆盖真实视频。
- **在什么时候**：2026-10-19 23:10
