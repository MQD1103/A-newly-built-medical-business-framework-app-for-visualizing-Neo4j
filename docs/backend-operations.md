# 后端提醒通知、安全与运维说明

本文件覆盖第二阶段的后端能力：提醒调度与站内通知、登录限流、密钥配置、
健康检查与日志、数据库备份 / 恢复 / 重建、MySQL 正式库。商城业务规则见
[`mall-backend.md`](mall-backend.md)，接口清单见
[`api-reference.md`](api-reference.md)，交互式文档仍以启动后的
`http://127.0.0.1:8000/docs`（Swagger）为准。

> 所有命令在仓库根目录执行；Windows 下使用 `backend\.venv\Scripts\python.exe`
> 或先激活虚拟环境。示例中的时间、路径按本机实际情况替换。

## 1. 环境变量

后端只从环境变量读取配置，不读取 `.env` 文件；真实密钥、密码、第三方 Token
不得写入仓库或文档。本机演示可不配置，上线前必须配置下列标 ★ 项。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| ★ `JWT_SECRET_KEY` | 内置演示密钥 | JWT 签名密钥。未配置时启动日志会告警，演示可用，上线必须更换为足够长的随机串。 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080`（7 天） | 登录令牌有效期（分钟）。 |
| `DATABASE_URL` | `sqlite:///./edu.db` | 数据库连接串。默认相对启动目录，建议生产用绝对路径，避免从不同目录启动时连到不同库。正式库可指向 MySQL，见 5.5。 |
| `REMINDER_SCAN_SECONDS` | `60` | 提醒扫描间隔（秒）；`0` 表示关闭后台调度器。 |
| `LOGIN_RATE_LIMIT` | `10` | 同一 IP + 用户名在窗口内允许的失败次数。 |
| `LOGIN_RATE_WINDOW_SECONDS` | `300` | 登录限流窗口（秒）。 |
| `LOGIN_IP_LIMIT` | `30` | 同一 IP 在窗口内允许的失败总次数。 |
| `MALL_AUTO_REFUND` | `1` | `0` 关闭商城自动退款，改为人工审核（详见商城文档）。 |
| `MALL_PAYMENT_CALLBACK_TOKEN` | 空 | 支付回调校验 Token；配置后回调必须携带一致值。 |
| `HOSPITAL_API_BASE_URL` | 空 | 真实医院接口根地址；为空时只能使用演示医院。 |
| `HOSPITAL_API_TOKEN` | 空 | 调用医院接口的 Bearer Token。 |
| `HOSPITAL_API_TIMEOUT_SECONDS` | `8` | 医院接口超时（1～30 秒）。 |
| `HOSPITAL_SYNC_LIMIT` / `HOSPITAL_SYNC_WINDOW_SECONDS` | `6` / `300` | 单用户手动同步医院的频率限制。 |
| `AI_DETECTOR_URL` / `AI_DETECTOR_TOKEN` | 空 | AI 用药检测服务地址与凭据；为空时使用演示模式。 |
| `AI_DETECTOR_TIMEOUT_SECONDS` | `10` | 检测服务超时，失败重试一次。 |
| `AI_IMAGE_MAX_MB` | `5` | 单张检测图片大小上限。 |
| `AI_RATE_LIMIT` / `AI_RATE_WINDOW_SECONDS` | `12` / `60` | 单用户检测频率限制。 |
| `AI_RESULT_RETENTION_DAYS` | `30` | 检测结果摘要保留天数，过期自动删除。 |

本机临时配置示例（PowerShell）：

```powershell
$env:JWT_SECRET_KEY = "换成一串足够长的随机字符"
$env:REMINDER_SCAN_SECONDS = "30"
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

> 默认 SQLite 适合本机演示与小队共享。需要正式信息库时可切换到 MySQL（5.5）；
> 现阶段最省事的共享方式仍是「一台机器跑后端，其他人连它的 API」。

## 2. 提醒与站内通知

### 2.1 概念

- **提醒（Reminder）** 是规则：标题、内容、到期时间、关联课程 / 目标用户。
- **通知（Notification）** 是触发记录，进入每个用户自己的收件箱。
- 同一用户、同一提醒、同一触发档位只生成一条通知，由数据库唯一约束
  `uq_notification_trigger` 兜底，多进程重复扫描也不会重复。

### 2.2 触发档位

| 档位 | 条件 | 正文前缀 |
|------|------|----------|
| `7d` | 距到期 1～7 天 | 还有 7 天到期 |
| `1d` | 距到期 1 天以内、尚未到期 | 明天到期 |
| `due` | 已到期且未超过 7 天 | 今天到期 / 已到期 |

- 扫描范围：到期时间在 **过去 7 天～未来 7 天** 内的提醒。
- 新建或编辑提醒时立即同步一次；后台任务每 `REMINDER_SCAN_SECONDS` 秒补扫。
- 已过档位不会重复补发。若服务停摆超过「到期 + 7 天」，该提醒不再生成通知。
- 已完成、关闭通知的用户不会收到新档位通知（见 2.3、2.4）。

### 2.3 谁收到通知

1. 指定了 `target_user_id`：只发给该用户。
2. 关联课程：课程教师 + 有效期内的一对一报名学员 + 有效期内整包报名学员。
   「有效」与商城学习权一致，过期报名不触达。
3. 个人提醒，或没有关联课程的提醒：发给创建者。
4. 系统级且没有创建者的提醒：发给全部用户。

### 2.4 通知偏好与完成状态

- 管理者 / 系统发布的提醒，用户可关闭「是否提醒」（`reminder_prefs`），
  只影响本人，关掉后不再生成新档位通知。
- 「已完成」按用户单独记录（`reminder_completions`），互不影响。
- 标记完成时，该提醒下本人所有未读通知一并转为已读；首页「临近提醒」不再显示。
- 取消完成后，后续扫描可以继续生成尚未生成过的档位。
- 个人提醒不需要偏好开关，也不能被他人删除。

### 2.5 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notifications` | 收件箱，支持 `unread_only`、`page`、`page_size`；返回 `items/total/unread`。 |
| GET | `/api/notifications/summary` | 未读数与最新一条，适合角标。 |
| POST | `/api/notifications/{id}/read` | 单条已读；他人的通知返回 403。 |
| POST | `/api/notifications/read-all` | 全部已读，返回 `updated` 条数。 |
| GET | `/api/home` | 首页聚合，新增 `unread_notifications`。 |
| POST | `/api/reminders/{id}/complete` | 请求体 `{"completed": true}`；传 `false` 取消。 |
| PUT | `/api/reminders/{id}/notify` | 请求体 `{"enabled": false}`；仅管理者 / 系统提醒可用。 |

示例：

```bash
curl -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/notifications?unread_only=true&page_size=20"
```

## 3. 登录限流

- 键：`IP + 小写用户名`（默认 10 次 / 5 分钟）与 `IP`（默认 30 次 / 5 分钟）。
- 只统计**失败**的登录；成功登录会清空该用户名的失败记录。
- 超限返回 `429`，`detail` 给出等待时间，并带 `Retry-After` 响应头。
- 计数保存在进程内存，单机演示足够；多实例部署需改用 Redis 等共享存储，
  否则每个实例各自计数。

## 4. 健康检查与日志

### 4.1 健康检查

`GET /api/health` 不需要登录：

```json
{"status": "ok", "database": "ok", "time": "2026-10-19T14:30:00.000000Z"}
```

数据库不可用时返回 `status=degraded`、`database=error`，并在日志中记录异常。
排障时先看这里，可快速区分「前端问题」与「后端 / 数据库问题」。

### 4.2 访问日志

统一格式：

```
2026-10-19 22:23:04 INFO [app.access] GET /api/notifications -> 200 8.9ms id=45e4d061ebeb client=127.0.0.1
```

- 只记录方法、路径（不含查询串）、状态码、耗时、请求 ID、客户端地址。
- **不记录请求体**，避免密码、患者信息、订单明细进入日志。
- 响应带 `X-Request-ID`；客户端也可传入该头，便于串联前后端问题。
- 4xx 记 WARNING，5xx 记 ERROR，未捕获异常会记录堆栈。

## 5. 数据备份、恢复与重建

脚本位于 `backend/scripts/`，默认操作 `backend/edu.db`，与当前工作目录无关。
`backend/backups/` 已加入 `.gitignore`，备份文件**不得**提交或外发。

### 5.1 备份

服务运行中也可以执行（使用 SQLite 在线备份 API，并做完整性检查）：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\backup_db.py
backend\.venv\Scripts\python.exe backend\scripts\backup_db.py --keep 30
```

- 输出 `backend/backups/edu-YYYYmmdd-HHMMSS.db`。
- 默认保留最近 14 份，超出自动清理。
- 可选 `--db <路径>`、`--out-dir <目录>`。

### 5.2 恢复

**先停止后端服务**，再执行：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\restore_db.py --backup backend\backups\edu-20261019-221000.db --yes
```

- 不带 `--yes` 只提示、不改动任何文件。
- 恢复前先把当前库快照为 `edu-before-restore-*.db`。
- 会校验备份与恢复结果的 `PRAGMA integrity_check`。
- 恢复后重启后端，前端 `Ctrl + F5`。

### 5.3 重建演示库

会清空现有业务数据，**先停止服务并确认**：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\rebuild_demo_db.py --yes
```

- 自动快照现有库为 `edu-before-rebuild-*.db`。
- 重新建表、执行 `ensure_schema()` 迁移、灌入演示数据。
- 完成后打印用户 / 课程 / 课时 / 服务商品数量，异常为空会报错退出。

### 5.4 表结构迁移

- 启动时执行 `Base.metadata.create_all` + `ensure_schema()`：
  新表自动创建，老库自动补列、回填默认值、补索引。
- 已用「商城主流程完成后、引入通知功能前」的旧库副本验证：
  启动后新增 `notifications`、`reminder_completions` 表，
  原有用户、课程、报名、提醒数据均保留。
- 迁移不会删除旧列或旧数据；重大结构变更仍建议先备份。

### 5.5 正式库 MySQL

需求 7.3 的正式信息库可使用 MySQL 8（utf8mb4）。当前代码已支持通过
`DATABASE_URL` 切换，SQLite 仍是默认的本机演示库。

1. 在 MySQL 中新建空库与专用账号（密码只放环境变量，不写入仓库）：

   ```sql
   CREATE DATABASE xiaoyi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'xiaoyi_app'@'%' IDENTIFIED BY '<强密码>';
   GRANT ALL PRIVILEGES ON xiaoyi.* TO 'xiaoyi_app'@'%';
   ```

2. 安装依赖（已包含纯 Python 驱动 PyMySQL，无需额外系统客户端）：

   ```powershell
   backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```

3. 设置连接串并启动。密码含特殊字符时需按 URL 规则转义：

   ```powershell
   $env:DATABASE_URL = "mysql+pymysql://xiaoyi_app:<密码>@127.0.0.1:3306/xiaoyi?charset=utf8mb4"
   $env:JWT_SECRET_KEY = "换成一串足够长的随机字符"
   backend\.venv\Scripts\python.exe -m uvicorn app.main:app
   ```

4. 首次启动会自动建表并灌入演示数据，随后可用 `/api/health` 确认连接。

注意：

- 只支持**由本项目新建的空 MySQL 库**。SQLite 旧数据不会自动迁入，
  已有业务数据请用导入脚本或人工迁移，迁移前先备份。
- `schema_migrate.py` 中重建表等 SQLite 专用逻辑不会在 MySQL 上执行；
  简单的补列仍可自动完成。正式环境的结构变更建议使用 Alembic 管理。
- 备份 / 恢复 / 演示库重建脚本目前只针对 SQLite。MySQL 请使用
  `mysqldump` / `mysql` 并纳入定期任务；备份文件同样不得提交仓库。
- 多实例部署时，登录限流等进程内状态需改为 Redis 等共享存储。

> 验证状态：33 张表、149 条建表语句已用 SQLAlchemy 的 MySQL 方言离线编译通过；
> 尚未连接真实 MySQL 实例联调。正式切换前请在测试库完整启动一次，
> 并跑一遍 `smoke_mall.py` 等冒烟测试。

## 6. 上线前检查清单

- [ ] 已配置 `JWT_SECRET_KEY`，启动日志不再出现演示密钥告警。
- [ ] 已确认 `DATABASE_URL` 指向预期数据库，且该文件不在 Git 中。
- [ ] 如使用 MySQL，已建空库与专用账号、配置 `charset=utf8mb4`，
      并使用 `mysqldump` 安排定期备份。
- [ ] CORS 已按实际部署收紧（当前开发配置为 `allow_origins=["*"]`）。
- [ ] 已配置 `MALL_PAYMENT_CALLBACK_TOKEN`（如启用回调）。
- [ ] 如接入真实医院，已配置 `HOSPITAL_API_BASE_URL` / `HOSPITAL_API_TOKEN`，
      并确认缓存期限、加密与删除策略（见 `hospital-integration.md`）。
- [ ] 如接入 AI 检测，已配置 `AI_DETECTOR_URL` / `AI_DETECTOR_TOKEN`，
      并确认服务方是否留存影像、留存时长与隐私说明（见 `ai-medication-check.md`）。
- [ ] 已安排定期备份，并实际演练过一次恢复。
- [ ] 日志中确认没有患者明细、完整病历、证件号、密码或 Token。
- [ ] `/api/health` 返回 `ok`，`/docs` 可访问（或按部署要求关闭）。
- [ ] 登录限流阈值符合部署规模；多实例部署已更换为共享限流存储。

## 7. 已验证内容

仓库内冒烟测试都会在临时目录新建独立数据库并启动真实后端，
不会读写 `backend/edu.db`：

| 脚本 | 检查数 | 覆盖范围 |
|------|--------|----------|
| `smoke_mall.py` | 67 | 登录、目录、试看、下单 / 支付 / 取消、退款规则、升级、团购与激活码、部分退款、服务订单、支付回调、管理员、旧接口 |
| `smoke_notifications.py` | 41 | 健康检查、旧库 / 新库建表、429 限流、三档提醒、通知偏好、完成隔离、已读、后台补发与幂等 |
| `smoke_hospital.py` | 52 | 合作医院开通、授权与撤销、只读缓存、同步限流、照护者授权、HTTP 对接、上游故障、日志脱敏 |
| `smoke_ai.py` | 41 | 图片校验、检测调用、失败摘要、用户隔离、限流、图片不入库、日志不含影像与 Token |

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smoke_mall.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_notifications.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_hospital.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_ai.py
```

接口参考文档由代码自动生成，接口改动后重新执行：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\export_api_doc.py
```

## 技术文档（按需求 5.3 四项）

- **操作人**：Claude Code（AI 开发助手；提交时请按团队要求替换为实际提交人姓名）
- **更改什么**：
  - 新增 `backend/app/notification_service.py`、`backend/app/observability.py`、
    `backend/app/rate_limit.py`、`backend/app/routers/notifications.py`；
  - 修改 `models.py`、`schemas.py`、`routers/reminders.py`、`routers/home.py`、
    `routers/auth.py`、`auth.py`、`database.py`、`main.py`；
  - 新增 `backend/scripts/backup_db.py`、`restore_db.py`、`rebuild_demo_db.py`、
    `smoke_notifications.py`；
  - 更新 `.gitignore`、`README.md` 与本文件。
- **作用是什么**：补齐需求 7.10 / 7.13 / 7.14 与安全 7.8——提醒可按
  7 天 / 1 天 / 到期三档自动生成站内通知，支持按人完成、通知开关、未读与已读；
  登录具备基础频率限制；JWT 密钥与数据库地址可通过环境变量配置；
  提供健康检查、脱敏访问日志，以及可执行的备份 / 恢复 / 演示库重建脚本。
- **在什么时候**：2026-10-19 22:25

## 技术文档（7.3 / 7.6 / 7.15 补充）

- **操作人**：Claude Code（AI 开发助手；提交时请按团队要求替换为实际提交人姓名）
- **更改什么**：
  - `schema_migrate.py` 改用 SQLAlchemy 反射补列 / 补索引，拼接与重建逻辑按
    SQLite / MySQL 方言分支；
  - `database.py` 为非 SQLite 连接增加 `pool_pre_ping` 与连接回收；
  - `requirements.txt` 增加 `PyMySQL`；
  - 新增 `backend/scripts/smoke_mall.py` 与 `backend/scripts/export_api_doc.py`，
    生成 `docs/api-reference.md`；
  - 更新本文件与 `README.md`。
- **作用是什么**：补齐需求 7.3 / 7.6 / 7.15——正式库可切换到 MySQL 8；
  接口参考文档由代码自动导出，避免与实现脱节；商城登录、下单、支付、
  退款、升级、团购、服务订单、回调与管理员流程纳入可重复执行的自动冒烟测试。
- **在什么时候**：2026-10-19 22:50
