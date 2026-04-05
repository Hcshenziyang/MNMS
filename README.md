# Project Phoenix - AI 面试助手

当前版本已从 `Django + MySQL` 重构为 `FastAPI + PostgreSQL + RabbitMQ + Redis + Vue`，核心目标是：

- 用更清晰的分层结构替代 Django 单体式耦合
- 用 PostgreSQL 替代 MySQL，统一面向生产级事务与 JSONB 能力
- 用 RabbitMQ + Celery 承接 LLM / RAG 等慢任务，避免 Web 进程被长请求拖死
- 以工程完整性、安全性、可解释性为第一优先级

## 快速启动

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 编辑 `.env`，至少确认：

- `APP_SECRET_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `RABBITMQ_URL`
- `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`（可选，不填会走离线回退）

3. 启动容器：

```bash
docker compose up --build
```

4. 访问地址：

- 前端：`http://localhost`
- FastAPI 健康检查：`http://localhost:8000/api/v1/health`
- FastAPI 文档：`http://localhost:8000/docs`
- RabbitMQ 管理台：`http://localhost:15672`

## 本地开发

### 后端

```bash
cd backend
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python scripts/build_vector_store.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Celery Worker

```bash
cd backend
celery -A app.core.celery_app.celery_app worker --loglevel=info --concurrency=2 -Q phoenix.ai
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## API 概览

Base URL: `/api/v1`

- `POST /auth/register`
- `POST /auth/login`
- `POST /jd/analyze`
- `POST /resume/optimize`
- `POST /interview/chat`
- `GET /jobs/{job_id}`
- `GET /health`

说明：

- 认证改为 JWT。
- AI 任务改为异步投递，接口先返回 `job_id`，前端再轮询任务状态。
- RAG 向量索引仍使用本地 FAISS 文件，但初始化与构建过程已从 Django 脚本迁移出来。

## 关键文档

- `docs/REFACTOR_OVERVIEW_ZH.md`
- `docs/HIGH_CONCURRENCY_GUIDE_ZH.md`
- `docs/LEARNING_ROADMAP_ZH.md`

## 目录结构

```text
backend/
  app/
    api/
    core/
    db/
    schemas/
    services/
    tasks/
    agent_engine/
  alembic/
  scripts/
frontend/
docs/
docker-compose.yml
```

## 迁移说明

- 老的 Django 目录仍保留在仓库里作为对照参考，但当前运行入口已经切换到 FastAPI。
- 如果你后续想彻底清理旧代码，可以在确认新链路稳定后再删除原有 `phoenix_project/` 与 `apps/` 目录。
