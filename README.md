# 小医 · 医疗独特商业框架（Web 优先）

面向医疗独特商业场景的辅助门户：公告、提醒、服务与课表、社区、COPD 售课与商城。后端 API 可复用给后续手机端。

**仓库地址：**  
https://github.com/MQD1103/A-newly-built-medical-business-framework-app-for-visualizing-Neo4j

## 协作方式（推荐）

**GitHub = 代码 + 历史记忆**；**每人在自己电脑跑前后端**，互不依赖、不用占对方电脑。

```
你推代码到 GitHub  →  同事 git clone / pull  →  各自双击「启动系统.bat」
                         ↓
              每人自己的 http://127.0.0.1:5173
              每人自己的本地数据库（互不影响）
```

- 关电脑也没关系：别人照样用自己的本机服务。
- Git 提交会保留每次改动，可随时回退。
- 业务数据在各自电脑的 `backend/edu.db`，**不会**同步到 GitHub（故意忽略，避免互相覆盖）。

## 技术栈

- 后端：Python FastAPI + SQLite + JWT（本机端口 **8000**）
- 前端：React + Vite + TypeScript（本机端口 **5173**）

## 新人：下载并启动（推荐）

**需要先安装：** Python 3.10+、Node.js（安装时勾选加入 PATH）。

```bat
git clone https://github.com/MQD1103/A-newly-built-medical-business-framework-app-for-visualizing-Neo4j.git
cd A-newly-built-medical-business-framework-app-for-visualizing-Neo4j
```

然后直接双击 **`启动系统.bat`**（首次会自动创建 `.venv`、安装 pip / npm 依赖，可能要几分钟）。
启动完成后会自动用浏览器打开前端 http://127.0.0.1:5173/；
如果前后端已经在运行，双击后会立即打开前端，不再停留。

浏览器打开：http://127.0.0.1:5173  

API 文档：http://127.0.0.1:8000/docs  

**只想打开前端？** 双击 **`打开前端.bat`**：前端已在运行会直接用浏览器打开
http://127.0.0.1:5173/；尚未运行则自动启动前后端后再打开。

### 首次打开应看到

- **首页**：蓝色节点图（服务 / 提醒 / 公告 / 商城 / 社区）
- **课程**：COPD 免费入门课、5 门单课与系统课整包（带彩色封面，单课演示价约 ¥2.99）

本机开发时 **不必改** `.env`：前端默认通过 Vite 代理连本机 `8000`。

### 若首页或课程不对

1. 双击 `关闭系统.bat`
2. 删除本机 `backend\edu.db`
3. 再双击 `启动系统.bat`（会按最新种子重建演示数据）
4. 浏览器 `Ctrl + F5` 强制刷新

## 日常改代码

```bat
git pull
# …改代码…
git add .
git commit -m "说明本次改了什么"
git push origin main
```

## 课程视频

课时视频有两套生成脚本，按内容质量从高到低使用：

1. **按课时内容生成的讲解片（推荐）**：封面 → 本节要点（取自课时摘要）→ 小结，
   24 秒 / 1280×720，保存到 `backend/uploads/courses/lessons/`，启动时自动挂载：

   ```bat
   backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
   backend\.venv\Scripts\python.exe backend\scripts\generate_lesson_videos.py
   ```

   常用参数：`--course-id 9` 只生成某门课；`--only-missing` 只补空缺；`--force` 重新生成。
   有 ffmpeg 时也可设环境变量 `FFMPEG_BIN` 指向 ffmpeg.exe，跳过 pip 安装 imageio-ffmpeg。

2. **10 秒色块演示片**：`backend/scripts/generate_demo_videos.py`，输出到
   `backend/uploads/courses/demo/`（已被 Git 忽略），仅在没有讲解片时兜底挂载。

两个脚本都只补空地址、不覆盖管理员填写的真实视频。换成正式课程视频时，
用管理中心填写真实视频地址即可。也可以用自己的本地片源（**请先确认版权/授权**），
`generate_demo_videos.py --source 片段.mp4` 会统一裁成 1280×720 并去掉音轨。

## 学习权有效期与续期

- 付费课程默认**买断 2 年**（`valid_days=730`），到期前 30 天课程页提示「还剩 N 天」；
- 过期后课程显示「已过期」，可用 `POST /api/courses/{id}/renew` 续期：
  新到期时间 = 原到期时间 + 2 年，剩余天数不吞；详见 `docs/mall-backend.md` 2.1 节。

## 演示账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 用户 | s2024001 | stu123 |
| 管理员 | admin | admin123 |

## 功能概览

- 登录与角色（用户 / 管理员）
- 节点首页导航、通知公告、提醒、课表与校历
- 社区动态、COPD 课程售卖、资料与成绩
- 商城：免费入门 / 单课 / 整包、试看、课时进度、订单支付、
  7 天内且进度低于 20% 退款、补差价升级、团购激活码、服务商品、
  课程两年有效期（到期提醒 / 续期不吞剩余天数）
- 站内通知：提醒 7 天 / 1 天 / 到期三档自动触达，支持按人完成、通知开关、已读
- 手机通知：用户授权后推送到手机通知栏，点击回到对应页面；支持多设备、
  测试通知、失效订阅自动清理（需 HTTPS，见通知文档）
- 安全与运维：登录限流、JWT / 数据库环境变量、健康检查、脱敏访问日志、
  数据库备份与演示库重建；正式库可切换 MySQL 8（utf8mb4）
- 医院对接：合作医院开通、用户授权、嘱托 / 病情 / 病历摘要只读缓存、
  照护者授权、医生嘱托转提醒
- AI 用药动作检测：图片校验、用户限流、检测服务适配、只存步骤摘要、
  原始影像不入库、按天自动清理
- 关联信息填写（家人 / 医院等）
- 管理中心：账号、课程、订单与退款、关联（仅管理员）

商城接口与业务规则见 [`docs/mall-backend.md`](docs/mall-backend.md)；
通知调度、环境变量、日志与备份恢复见
[`docs/backend-operations.md`](docs/backend-operations.md)；
医院对接与只读授权见
[`docs/hospital-integration.md`](docs/hospital-integration.md)；
手机通知的密钥配置、HTTPS 要求与接口见
[`docs/mobile-notifications.md`](docs/mobile-notifications.md)；
AI 用药检测的服务端约定见
[`docs/ai-medication-check.md`](docs/ai-medication-check.md)；
全部接口清单见 [`docs/api-reference.md`](docs/api-reference.md)
（由 `backend/scripts/export_api_doc.py` 根据代码自动生成）。

## 目录

```
backend/               FastAPI（本机 8000）
backend/scripts/       商城 / 通知 / 医院 / AI 检测冒烟测试、接口文档导出、
                       数据库备份 / 恢复 / 重建
frontend/              Vite React（本机 5173）
frontend/.env.example  可选：自定义后端地址（一般留空）
启动系统.bat / 关闭系统.bat / 打开前端.bat
```

备份命令示例（备份文件在 `backend/backups/`，已被 Git 忽略）：

```bat
backend\.venv\Scripts\python.exe backend\scripts\backup_db.py
```
