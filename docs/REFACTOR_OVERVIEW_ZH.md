# 重构总览

这次重构不是“把 Django 视图改写成 FastAPI 路由”这么简单，而是把后端整体运行方式一起换掉了。

## 1. 技术栈变化

| 维度 | 重构前 | 重构后 | 变化原因 |
| --- | --- | --- | --- |
| Web 框架 | Django + DRF | FastAPI | 接口层更轻，依赖注入更直观，适合显式分层 |
| 数据库 | MySQL | PostgreSQL | 更适合事务、JSONB、复杂查询和后续扩展 |
| ORM | Django ORM | SQLAlchemy 2.0 + Alembic | 把模型、会话、迁移过程显式化 |
| 异步任务 | 无 | RabbitMQ + Celery | 把 LLM / RAG 慢任务从 Web 进程中剥离 |
| 认证 | 请求体用户名 | JWT | 提升安全性，避免伪造用户上下文 |
| 缓存 | Django cache + Redis | Redis + 本地降级缓存 | 去掉 Django 运行时依赖 |

## 2. 目录结构变化

### 新后端主目录

```text
backend/app/
  api/        # FastAPI 路由与依赖
  core/       # 配置、数据库、JWT、安全中间件、Celery
  db/         # SQLAlchemy 模型
  schemas/    # Pydantic 请求/响应模型
  services/   # 认证、任务、缓存等服务层
  tasks/      # Celery 异步任务
  agent_engine/ # 原 PhoenixAgent 能力迁移后的框架无关层
```

### 旧目录现状

- `backend/phoenix_project/` 和 `backend/apps/` 目前保留，作用是给你做对照学习。
- 当前真正运行入口已经改成 [backend/app/main.py](/d:/data/code/MNMS/backend/app/main.py)。

## 3. 核心行为变化

### 认证

重构前：

- 前端把 `username` 放进请求体
- 后端按 `username` 找或创建 Django `User`

重构后：

- 先走 `register/login`
- 后端签发 JWT
- 业务接口统一通过 `Authorization: Bearer <token>` 获取当前用户

对应代码：

- [auth.py](/d:/data/code/MNMS/backend/app/api/routers/auth.py)
- [security.py](/d:/data/code/MNMS/backend/app/core/security.py)
- [deps.py](/d:/data/code/MNMS/backend/app/api/deps.py)

### 数据持久化

重构前：

- Django ORM 隐式管理连接、事务和模型

重构后：

- SQLAlchemy 2.0 明确区分 `AsyncSession` 和同步 `Session`
- Alembic 负责数据库迁移

对应代码：

- [database.py](/d:/data/code/MNMS/backend/app/core/database.py)
- [models.py](/d:/data/code/MNMS/backend/app/db/models.py)
- [20260405_01_initial_fastapi_stack.py](/d:/data/code/MNMS/backend/alembic/versions/20260405_01_initial_fastapi_stack.py)

### AI 请求链路

重构前：

- 用户请求直接进入 Django 视图
- 视图里直接调用 Agent / LLM
- Web worker 在等待期间被占住

重构后：

- FastAPI 路由只负责参数校验、鉴权、创建任务
- RabbitMQ 负责投递
- Celery worker 真正执行 Agent / LLM / RAG
- 前端通过 `job_id` 轮询结果

对应代码：

- [jd.py](/d:/data/code/MNMS/backend/app/api/routers/jd.py)
- [resume.py](/d:/data/code/MNMS/backend/app/api/routers/resume.py)
- [interview.py](/d:/data/code/MNMS/backend/app/api/routers/interview.py)
- [worker.py](/d:/data/code/MNMS/backend/app/tasks/worker.py)

## 4. 你最该先理解的几个文件

如果你要从 Django 思维切到 FastAPI 思维，建议按这个顺序看：

1. [main.py](/d:/data/code/MNMS/backend/app/main.py)
2. [deps.py](/d:/data/code/MNMS/backend/app/api/deps.py)
3. [models.py](/d:/data/code/MNMS/backend/app/db/models.py)
4. [jobs.py](/d:/data/code/MNMS/backend/app/services/jobs.py)
5. [worker.py](/d:/data/code/MNMS/backend/app/tasks/worker.py)

## 5. 这次重构真正解决了什么

- 旧版本把 Web 请求、慢任务、鉴权、缓存、数据访问揉在一起，后期很难继续扩。
- 新版本把“入口层”“业务编排”“慢任务执行”“数据库迁移”拆开了。
- 这样你后续继续学习时，不会再把 FastAPI 误解成“另一个写视图的框架”，而会看到它和 PostgreSQL、RabbitMQ 是怎么作为一套工程一起工作的。
