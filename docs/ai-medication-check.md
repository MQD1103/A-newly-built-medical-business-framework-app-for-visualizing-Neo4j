# AI 用药动作检测（服务端配合）

对应需求 7.11。前端负责拍摄与展示；后端负责鉴权、调用检测服务、限流与
保存结果摘要。

## 1. 边界

- 只判断「步骤是否完成 / 哪一步需要重做」，不生成药效、诊断、调药结论。
- **不保存原始影像**：图片只在内存中处理，调用完即丢弃，数据库无图片列。
- 结果摘要仅本人可见，按保留天数自动清理。
- 检测服务异常时返回可理解提示，引导用户重试或回看课程。
- 医院 / 检测服务地址与 Token 只放环境变量，不写入仓库、不写日志。

## 2. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AI_DETECTOR_URL` | 空 | 检测服务地址。为空时使用内置演示模式。 |
| `AI_DETECTOR_TOKEN` | 空 | 调用检测服务的 Bearer Token。 |
| `AI_DETECTOR_TIMEOUT_SECONDS` | `10` | 单次调用超时（1～60 秒），失败重试一次。 |
| `AI_IMAGE_MAX_MB` | `5` | 单张图片大小上限（0.2～20 MB）。 |
| `AI_RATE_LIMIT` | `12` | 单个用户在窗口内最多检测次数。 |
| `AI_RATE_WINDOW_SECONDS` | `60` | 限流窗口（秒）。 |
| `AI_RESULT_RETENTION_DAYS` | `30` | 结果摘要保留天数（1～365 天），过期自动删除。 |

## 3. 接口

### POST `/api/ai/medication-checks`

`multipart/form-data`：

| 字段 | 必填 | 说明 |
|------|------|------|
| `file` | 是 | JPG / PNG / WebP，单张不超过 `AI_IMAGE_MAX_MB`。 |
| `lesson_id` | 否 | 关联课时，便于前端在课程页发起检测。 |

成功响应：

```json
{
  "id": 12,
  "user_id": 3,
  "lesson_id": 5,
  "status": "completed",
  "provider": "http",
  "steps": [
    {"name": "核对药名", "done": true},
    {"name": "完成本次用药动作", "done": false}
  ],
  "needs_retry": true,
  "message": "请按提示重做未完成步骤。",
  "image_size": 204800,
  "image_type": "image/jpeg",
  "created_at": "2026-10-19T14:40:00",
  "expires_at": "2026-11-18T14:40:00",
  "disclaimer": "结果仅表示步骤是否完成，不构成诊断或用药建议；如有不适请咨询医生。"
}
```

失败时返回：

| 状态码 | 场景 |
|--------|------|
| 400 | 非 JPG/PNG/WebP、内容与类型不符、空图片 |
| 404 | 关联课时不存在 |
| 413 | 图片超过大小限制 |
| 429 | 触发用户检测频率限制，带 `Retry-After` |
| 502 | 检测服务鉴权失败、网络异常、返回格式异常 |
| 503 | 检测服务未配置或繁忙 |

检测失败也会保存一条脱敏摘要（`status=failed`、无步骤、保留错误提示），
方便用户回看「这次为什么失败」，不保存图片。

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ai/medication-checks?page=&page_size=` | 本人历史摘要，返回 `total`、`retention_days`、合规声明 |
| GET | `/api/ai/medication-checks/{id}` | 单条详情；他人记录返回 404 |
| DELETE | `/api/ai/medication-checks/{id}` | 本人撤回记录 |

## 4. 检测服务约定

配置 `AI_DETECTOR_URL` 后，后端以原始图片字节 POST 到该地址：

```text
POST {AI_DETECTOR_URL}
Content-Type: image/jpeg | image/png | image/webp
Authorization: Bearer {AI_DETECTOR_TOKEN}
X-Lesson-Id: 5
```

期望响应：

```json
{
  "steps": [
    {"name": "核对药名", "done": true},
    {"name": "完成本次用药动作", "done": false}
  ],
  "needs_retry": true,
  "message": "请按提示重做未完成步骤。"
}
```

- `steps` 最多取前 12 条，空名称会被忽略。
- `message` 截断到 500 字；检测服务不得返回药效、诊断或调药结论。
- 未配置 `AI_DETECTOR_URL` 时使用演示模式，响应 `provider=demo`，
  并明确提示「结果仅用于流程联调」。

## 5. 隐私与安全

- 图片不落盘、不入库、不写日志；数据库只存体积、类型和步骤摘要。
- 结果按用户隔离；他人的记录查询、删除均返回 404。
- 每人独立限流；鉴权失败与超限都不会触发检测调用。
- 摘要到期在用户新增 / 查询记录时自动清理。
- 正式上线前需与检测服务方确认：是否留存影像、留存时长、是否用于训练；
  若服务方留存，需在隐私说明中写明并取得用户同意。

## 6. 已验证

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smoke_ai.py
```

在临时库上启动真实后端与本地假检测服务，覆盖 41 项检查：
演示模式、图片类型 / 魔数 / 空文件 / 超限校验、课时关联、正常检测、
服务异常与格式异常、失败摘要、历史与详情、用户隔离、删除、
用户级限流与 `Retry-After`、数据库无图片列、日志无图片与 Token。
不会读写 `backend/edu.db`。

## 技术文档（按需求 5.3 四项）

- **操作人**：Claude Code（AI 开发助手；提交时请按团队要求替换为实际提交人姓名）
- **更改什么**：
  - 新增 `backend/app/ai_service.py`、`backend/app/routers/ai.py`、
    `backend/scripts/smoke_ai.py`、`docs/ai-medication-check.md`；
  - 修改 `backend/app/models.py`（`medication_checks` 表）、`schemas.py`、
    `main.py`、`README.md`、`docs/backend-operations.md`。
- **作用是什么**：补齐需求 7.11 的服务端配合——图片鉴权、格式与大小校验、
  用户级限流、检测服务调用与超时重试、只保存步骤摘要、历史查询与撤回；
  原始影像不入库、不写日志，结果仅本人可见并按天清理，不产生药效或诊断结论。
- **在什么时候**：2026-10-19 22:55
