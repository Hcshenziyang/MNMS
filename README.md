# Project Phoenix - AI 面试助手

基于 Django + DRF + Vue + MySQL + Redis + FAISS 的 Agent 化求职辅助系统，支持：

- 岗位分析（JD Analysis）
- 简历优化（Resume Optimization）
- 模拟面试（Mock Interview + RAG）

## 1. 快速启动（Docker）

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 编辑 `.env`，至少设置：
- `DJANGO_SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `OPENAI_API_KEY`（可选，不填则进入离线回退模式）

3. 启动服务：

```bash
docker compose up --build
```

4. 访问：
- 前端：`http://localhost`（若改了 `NGINX_PORT`，请用对应端口）
- 后端健康检查：`http://localhost:8000/api/v1/health`

## 2. 本地开发（非 Docker）

### 后端

```bash
cd backend
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
set DJANGO_SETTINGS_MODULE=phoenix_project.settings
python manage.py migrate
python scripts/build_vector_store.py
python manage.py runserver 0.0.0.0:8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认请求 `/api/v1`，本地开发可通过 Vite 代理或直接使用 Docker Nginx。

## 3. API 概览

Base URL: `/api/v1`

- `POST /jd/analyze`
- `POST /resume/optimize`
- `POST /interview/chat`
- `GET /health`

详见项目说明书：`PROJECT_MANUAL_ZH.md`

## 4. 主要目录

```text
backend/
  apps/
    api/
    core/
    agent_engine/
  data/
  scripts/
frontend/
docker-compose.yml
PROJECT_MANUAL_ZH.md
```

## 5. 说明

- 当前版本默认使用 `demo_user`（或请求体 `username`）进行多用户隔离。
- 若未配置 LLM API Key，系统会使用规则化回退策略，保证流程可用。
- 向量索引位于 `backend/data/vector_store/`，已配置 Docker Volume 持久化。