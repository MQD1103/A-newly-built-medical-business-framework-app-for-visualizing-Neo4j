# 小医 · 医疗独特商业框架（Web 优先）

面向医疗独特商业场景的辅助门户：公告、提醒、课表与校历、社区、资料与成绩。后端 API 可复用给后续手机端。

## 协作方式（推荐）

**GitHub = 代码 + 历史记忆**；**每人在自己电脑跑前后端**，互不依赖、不用占你的电脑。

```
你推代码到 GitHub  →  同事 git pull / clone  →  各自双击「启动系统.bat」
                         ↓
              每人自己的 http://127.0.0.1:5173
              每人自己的本地数据库（互不影响）
```

- 关电脑也没关系：别人照样用自己的本机服务。
- Git 提交会保留每次改动，可随时回退到「上一次」。
- 业务数据在各自电脑的 `backend/edu.db`，**不会**自动同步到 GitHub（已忽略，避免互相覆盖）。

若以后需要「全队共用同一份在线数据」，再单独把后端部署到云（Render / Railway 等），与本机开发无关。

## 技术栈

- 后端：Python FastAPI + SQLite + JWT（本机端口 **8000**）
- 前端：React + Vite + TypeScript（本机端口 **5173**）

## 新人：从 GitHub 拉代码并启动

```bat
git clone <仓库地址>
cd 医疗商业框架
```

**后端依赖（首次）：**

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

**前端依赖（首次）：**

```bat
cd frontend
npm install
cd ..
```

然后双击 `启动系统.bat`，浏览器打开：http://127.0.0.1:5173  

API 文档：http://127.0.0.1:8000/docs  

本机开发时 **不必改** `.env`：前端默认通过 Vite 代理连本机 `8000`。

## 日常改代码（保留历史）

```bat
git pull
git checkout -b feature/你的改动
# …改代码…
git add .
git commit -m "说明本次改了什么"
git push -u origin HEAD
```

在 GitHub 开 Pull Request，合并后历史永久保留。

## 演示账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 用户 | s2024001 | stu123 |
| 管理员 | admin | admin123 |

## 功能概览

- 登录与角色（用户 / 管理员）
- 通知公告、提醒、课表与校历
- 社区动态、课程资料与成绩
- 关联信息填写（家人 / 医院等）
- 管理中心：账号、课程、关联（仅管理员）

## 目录

```
backend/              FastAPI（本机 8000）
frontend/             Vite React（本机 5173）
frontend/.env.example 可选：自定义后端地址（一般留空）
启动系统.bat / 关闭系统.bat
```
