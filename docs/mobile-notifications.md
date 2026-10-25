# 手机通知（Web Push）

提醒到点后，除了站内消息列表，还可以推送到手机通知栏。点击通知会打开
前端对应页面（课程、提醒或消息列表）。

实现基于标准 Web Push：Service Worker + Push API + VAPID，不依赖第三方
推送 SDK；Android Chrome / Edge 与 iOS 16.4+（需添加到主屏幕）均可使用。

## 一次性配置

```bat
backend\.venv\Scripts\python.exe backend\scripts\generate_vapid_keys.py
```

脚本会在 `backend/.env` 写入：

```ini
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:admin@xiaoyi.local
```

- `.env` 已被 `.gitignore` 排除，**私钥不要提交仓库，也不要写进前端**。
- 重新生成密钥（`--force`）会使已开启的设备订阅全部失效，用户需要重新开启。
- 修改后重启后端。生产环境建议由部署平台直接注入这三个环境变量。
- 服务端只接受主流浏览器推送服务的地址（FCM / Mozilla / WNS / Apple）。
  自建推送服务时，用 `PUSH_ALLOWED_HOSTS=push.example.com` 追加允许域名。

## 使用流程

1. 打开「我的 → 消息通知」或「服务 → 消息通知」。
2. 点击「开启手机通知」，浏览器弹出权限提示时选择允许。
3. 点击「发送测试通知」确认手机通知栏能收到。
4. 之后的用药、复查提醒会在扫描器生成站内通知后自动推送，同一条只推一次。

前端会显示服务端是否已配置密钥、当前用户已授权的设备数；关闭通知只影响
当前设备，其它设备不受影响。

## 环境要求（重要）

浏览器只在**安全上下文**中允许注册 Service Worker 与推送：

| 场景 | 是否可用 | 说明 |
| --- | --- | --- |
| `http://127.0.0.1:5173` / `http://localhost:5173` | ✅ | 本机调试可直接用 |
| `http://局域网IP:5173` | ❌ | 手机访问必须使用 HTTPS |
| 正式 HTTPS 域名 | ✅ | 推荐；证书需被手机信任 |
| iOS Safari（普通标签页） | ❌ | 需先「添加到主屏幕」，从主屏幕打开 |
| iOS 主屏幕应用（16.4+） | ✅ | 仍需 HTTPS |

没有 HTTPS 时页面会给出提示，站内消息列表仍然可用，只是不会推送。

Android 调试小技巧：USB 连接后执行
`adb reverse tcp:5173 tcp:5173` 与 `adb reverse tcp:8000 tcp:8000`，
在手机浏览器打开 `http://localhost:5173` 即属于安全上下文。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/notifications` | 站内消息列表（含 `click_url`） |
| GET | `/api/notifications/push/config` | 公开配置：是否启用 + VAPID 公钥 |
| GET | `/api/notifications/push/status` | 当前用户的设备数与最近成功时间 |
| POST | `/api/notifications/push/subscribe` | 保存/更新浏览器订阅 |
| POST | `/api/notifications/push/unsubscribe` | 删除当前设备的订阅 |
| POST | `/api/notifications/push/test` | 发送测试通知（每用户 5 次/分钟） |

订阅保存时按 `endpoint` 去重，同一浏览器换账号登录会改归当前用户。
推送服务返回 404/410 时自动删除失效订阅；推送内容只取自站内通知，
不额外读取病历或医院数据。

## 隐私提示

- 通知标题与正文会显示在锁屏上；如涉及隐私，请在手机系统设置中关闭
  「通知预览」或只保留横幅。
- 推送订阅地址本身可作为投递凭据，数据库只保存必要字段，错误日志只记
  状态码，不记录完整地址。
- 「消息通知」页关闭的是当前设备；如需彻底停用，请在系统通知设置中
  关闭本应用。
