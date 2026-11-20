# 症状日记 / 用药打卡 / 随访提醒

三个自我管理模块，后端 API 可复用给手机端。全部只做记录与提醒，
**不提供诊断、不给用药建议**。

## 1. 症状日记

每天一条，记录咳嗽 / 气短 / 痰量（0–3 级）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/symptoms?days=30` | 近 N 天记录，含加重提示与免责声明 |
| POST | `/api/symptoms` | 写入；同一天再提交视为更新，不产生重复记录 |
| DELETE | `/api/symptoms/{id}` | 删除自己的记录 |

- 加重判定：任一症状达 3 级，或总分较上一次上升 ≥3。
- 不能记录未来日期（`400`）。

## 2. 用药打卡

「计划」是长期用药安排，「打卡记录」是每天每次的结果。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/medication/plans` | 计划列表（默认不含已停用，`?include_archived=true` 含） |
| POST | `/api/medication/plans` | 新建计划 |
| PATCH | `/api/medication/plans/{id}` | 改药名/剂量/次数/时间/状态；`clear_end_date=true` 清除结束日期 |
| DELETE | `/api/medication/plans/{id}` | 删除计划及其打卡记录 |
| GET | `/api/medication/today` | 今日待打卡清单，槽位自动补齐 |
| POST | `/api/medication/checkin` | 打卡：`taken` 已服用 / `skipped` 已跳过 / `pending` 撤销 |
| GET | `/api/medication/logs?days=30` | 打卡历史 |
| GET | `/api/medication/adherence?days=30` | 依从率与连续达标天数 |

约定：

- `times` 为逗号分隔的 `HH:MM`（如 `08:00,20:00`），个数不足补空、超出每日次数截断；
  格式非法返回 `400`。
- 今日槽位在查询 `/today` 时按 `frequency` 自动生成，前端不必先建后打。
- 同一计划同一天同一班次重复打卡是**更新**，靠唯一约束
  `(plan_id, take_date, slot)` 保证不重复。
- 计划状态 `active` / `paused` / `archived`，暂停后不再生成待打卡，也不计入应服。

### 依从率口径

- **应服次数按计划推算**（`每日次数 × 计划生效天数`），不是按已生成的打卡记录数。
  这样即便某天没打开应用也不会漏算。
- `missed = 应服 − 已服 − 已跳过`；`rate = 已服 / 应服`。
- `streak_days`：从今天往前，当天应服次数全部完成才算达标；没有计划的日期跳过不中断。

## 3. 随访提醒

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/followups` | 计划列表，含状态与剩余天数 |
| POST | `/api/followups` | 新建（自动挂提醒） |
| PATCH | `/api/followups/{id}` | 修改；暂停/结束会撤掉提醒，恢复时重新挂上 |
| DELETE | `/api/followups/{id}` | 删除计划、记录与影子提醒 |
| GET | `/api/followups/summary` | 汇总：各状态数量、下次随访 |
| GET | `/api/followups/{id}/visits` | 某计划的随访记录 |
| POST | `/api/followups/{id}/complete` | 完成一次随访，按周期滚动下次到期 |

- 类型：`outpatient` 门诊随访、`lung_function` 肺功能复查、`imaging` 影像复查、
  `phone` 电话随访、`other` 其他；周期 `interval_days` 7–730 天。
- 状态由 `next_due_date` 推算：`overdue` 已逾期 / `due_soon` 7 天内 /
  `upcoming` 未到期 / `closed` 已结束；`days_remaining` 负数表示逾期天数。

### 与通知链路的衔接

每条随访计划会挂一条**影子提醒**（`reminders` 表，`kind=checkup`、
`source=user`、`target_user_id=本人`），因此自动复用既有链路：

```
随访计划 → 影子提醒 → 提醒调度器 → 站内通知（7 天 / 1 天 / 到期三档）→ 手机推送
```

- 完成随访：本轮提醒标记完成（停止「已到期」推送），并为下一周期**另起一条提醒**
  （`recurring_parent_id` 指回上一条），历史保留、重新进入提醒窗口。
- 暂停或结束：撤掉影子提醒并清理其通知/完成状态，不再打扰；恢复时重新挂上。
- 用户在「提醒」页也能看到并操作这些随访提醒。

## 免责声明

三个模块的所有列表接口都带 `disclaimer` 字段，前端应原样展示：

- 症状日记：仅用于自我观察，出现明显气短、胸痛、咯血或持续加重请及时就医。
- 用药打卡：仅用于自我记录与复诊回顾，漏服或不适按医嘱处理或咨询医生。
- 随访提醒：按用户填写周期推算，不替代医生给出的复诊安排。

## 冒烟测试

```bat
backend\.venv\Scripts\python.exe backend\scripts\smoke_health_tracking.py
```

在临时库上启动真实后端进程，覆盖 54 项断言：建表、症状同日覆盖与加重提示、
打卡与撤销、依从率口径、随访状态判定、完成滚动、通知落地、暂停撤提醒、越权访问。
不读写 `backend/edu.db`。
