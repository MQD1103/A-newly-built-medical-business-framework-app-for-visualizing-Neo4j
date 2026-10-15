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

浏览器打开：http://127.0.0.1:5173  

API 文档：http://127.0.0.1:8000/docs  

### 首次打开应看到

- **首页**：蓝色节点图（服务 / 提醒 / 公告 / 商城 / 社区）
- **课程**：COPD 系列 5 门售课（带彩色封面，标价约 ¥2.99）

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

## 演示账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 用户 | s2024001 | stu123 |
| 管理员 | admin | admin123 |

## 功能概览

- 登录与角色（用户 / 管理员）
- 节点首页导航、通知公告、提醒、课表与校历
- 社区动态、COPD 课程售卖、资料与成绩
- 关联信息填写（家人 / 医院等）
- 管理中心：账号、课程、关联（仅管理员）

## 目录

```
backend/               FastAPI（本机 8000）
frontend/              Vite React（本机 5173）
frontend/.env.example  可选：自定义后端地址（一般留空）
启动系统.bat / 关闭系统.bat
```
##日志
10.16：
新增加好友功能
管理员功能优化升级


