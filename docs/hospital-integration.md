# 医院对接适配层（只读）

对应需求 7.9。医院相关逻辑集中在 `backend/app/hospital_service.py` 与
`backend/app/routers/hospital.py`，不散落在其他业务接口里。

> 医院资料全程只读：没有修改病历、开药、改医嘱的接口。真实医院地址、Token
> 只放环境变量，不写进仓库、不下发前端、不写日志。

## 1. 能力范围

- 合作医院开通 / 停用（管理员）
- 用户授权状态（授权、撤销、过期判断）
- 医生嘱托 / 病情说明 / 病历检查摘要的拉取与只读缓存
- 患者授权照护者查看自己的资料（可随时撤销）
- 医生嘱托在用户确认后转成个人提醒，进入既有提醒 / 通知体系
- 上游超时、鉴权失败、无授权、服务不可用等错误统一转成可理解提示

## 2. 数据表

| 表 | 作用 |
|----|------|
| `hospital_partners` | 合作医院：编码、名称、科室、启用状态、对接方式（`demo` / `http`） |
| `hospital_authorizations` | 用户对医院的授权：医院侧患者标识、范围、状态、有效期 |
| `hospital_records` | 只读资料缓存；按「用户 + 医院 + 外部 ID」去重 |
| `hospital_caregiver_grants` | 患者 → 照护者的查看授权，撤销后保留记录 |
| `hospital_reminder_links` | 由哪条医嘱生成了哪条提醒，便于追溯 |

新表由启动时的 `Base.metadata.create_all` 自动创建，旧库无需手工迁移。

## 3. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOSPITAL_API_BASE_URL` | 空 | 真实医院接口根地址，例如内网网关地址。为空时只能使用 `demo` 医院。 |
| `HOSPITAL_API_TOKEN` | 空 | 调用医院接口的 Bearer Token。 |
| `HOSPITAL_API_TIMEOUT_SECONDS` | `8` | 单次调用超时，限制在 1～30 秒。 |
| `HOSPITAL_SYNC_LIMIT` | `6` | 单个用户在窗口内最多手动同步次数。 |
| `HOSPITAL_SYNC_WINDOW_SECONDS` | `300` | 同步限流窗口（秒）。 |

## 4. 两种对接方式

- `demo`：内置「示范合作医院（演示）」，启动时自动创建。返回固定的演示嘱托、
  病情摘要和检查摘要，仅用于联调，不作为诊疗依据。
- `http`：管理员在后台开通后，后端请求：

```text
GET {HOSPITAL_API_BASE_URL}/patients/{patient_ref}/records
Authorization: Bearer {HOSPITAL_API_TOKEN}
Accept: application/json
```

期望响应（也接受顶层直接为数组）：

```json
{
  "items": [
    {
      "external_id": "advice-20261001-1",
      "record_type": "advice",
      "title": "复诊嘱托",
      "content": "按医嘱用药，按时复诊。",
      "doctor_name": "张医生",
      "department": "呼吸内科",
      "occurred_at": "2026-10-01T09:00:00"
    }
  ]
}
```

`record_type`：`advice`（医生嘱托）、`condition`（病情说明）、
`record`（病历 / 检查摘要）。缺 `external_id` 或标题的条目会被跳过。
上游超时或网络错误会重试一次，仍失败则返回「医院接口暂不可用」。

## 5. 接口

所有接口需要登录。`patient_id` 缺省表示本人；填其他用户时必须持有该患者
有效的照护授权。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/hospital/partners` | 已启用的合作医院 |
| GET | `/api/hospital/authorizations?patient_id=` | 授权列表（患者标识脱敏） |
| POST | `/api/hospital/authorizations` | `{partner_id, patient_ref, consent: true}` |
| DELETE | `/api/hospital/authorizations/{id}` | 撤销授权；缓存资料随即不可读 |
| POST | `/api/hospital/authorizations/{id}/sync` | 拉取并缓存只读资料 |
| GET | `/api/hospital/records?patient_id=&record_type=` | 只读资料列表 |
| GET | `/api/hospital/records/{id}` | 资料详情 |
| POST | `/api/hospital/records/{id}/reminder` | `{due_at, title?, content?}`，把医生嘱托转成个人提醒 |
| GET | `/api/hospital/caregivers` | 我授出的、我收到的照护授权 |
| POST | `/api/hospital/caregivers` | `{caregiver_username, relation}`，患者授权照护者 |
| DELETE | `/api/hospital/caregivers/{id}` | 患者或照护者撤销授权 |
| GET | `/api/hospital/admin/partners` | 管理员查看全部医院 |
| POST | `/api/hospital/admin/partners` | 管理员开通医院 |
| PATCH | `/api/hospital/admin/partners/{id}` | 改名称 / 科室 / 对接方式 / 启用状态 |

### 权限规则

- 只有管理员能开通、停用医院。
- 用户只能为自己提交或撤销授权；照护者只能读，不能替患者同步或建提醒。
- 读取资料要求对应医院授权仍在有效期内；撤销后即使缓存仍在也不返回。
- 医院停用后：不再出现在可选列表，也不能继续同步；已缓存资料在授权有效时
  仍可查看，避免停用操作误伤历史资料。
- 医生嘱托转提醒：只有资料所有者本人、且资料类型为 `advice` 才能操作。

### 提醒联动

`POST /api/hospital/records/{id}/reminder` 会创建一条个人提醒
（`source=user`，不关联课程），并立即走既有通知调度：
到期前 7 天、1 天、到期时各生成一次站内通知。提醒正文默认带
「来自某医院的医生嘱托」，用户可自行修改标题和内容。

## 6. 安全与隐私

- 医院侧患者标识在接口响应中脱敏（保留首尾各 2 位），日志完全不含该标识。
- 访问日志只记方法、路径、状态码、耗时、请求 ID、客户端 IP，不记请求体。
- 上游 Token 只在后端环境变量中，冒烟测试也校验日志不出现 Token。
- 资料缓存保存的是医院返回的文本摘要；生产接入前应和医院确认：
  缓存范围、保存期限、是否需要加密、撤销授权后是否立即物理删除。
- 当前授权流程是「用户填写医院患者标识并确认」的简化版。正式接入应改为
  医院 OAuth / 授权码换取访问凭据，后端不长期保存患者标识。

## 7. 已验证

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smoke_hospital.py
```

该脚本在临时库上启动真实后端与本地假医院接口，覆盖 52 项检查：
登录与权限、演示 / HTTP 两种模式、授权与撤销、同步缓存与去重、
资料隔离、照护者授权与撤销、医嘱转提醒、上游 500 错误与缓存保留、
患者标识与 Token 不入日志。不会读写 `backend/edu.db`。

## 技术文档（按需求 5.3 四项）

- **操作人**：Claude Code（AI 开发助手；提交时请按团队要求替换为实际提交人姓名）
- **更改什么**：
  - 新增 `backend/app/hospital_service.py`、`backend/app/routers/hospital.py`、
    `backend/scripts/smoke_hospital.py`、`docs/hospital-integration.md`；
  - 修改 `backend/app/models.py`（5 张医院对接表）、`schemas.py`、`main.py`、
    `seed.py`（演示医院）、`README.md`。
- **作用是什么**：补齐需求 7.9 的医院对接适配层——合作医院开通、用户授权、
  医生嘱托 / 病情说明 / 病历摘要的只读拉取与缓存、照护者授权、统一超时与错误
  处理；用户确认后可将医生嘱托转为提醒，复用 7.10 的通知调度。同时保证敏感
  读取有鉴权、患者标识脱敏、Token 与患者标识不进日志。
- **在什么时候**：2026-10-19 22:45
