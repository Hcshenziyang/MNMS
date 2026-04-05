# 学习路线图

你之前学的是 `Django + MySQL`，现在工作需要转到 `FastAPI + PostgreSQL + RabbitMQ`。这不是单纯换语法，而是思维模型也要切。

下面给你一个分层学习目录。你不需要一次学完，但顺序很重要。

## 第一层：先把 FastAPI 当成“显式版后端框架”

目标：先能读懂项目代码。

优先学习：

1. 路由和 `APIRouter`
2. `Depends` 依赖注入
3. Pydantic 请求/响应模型
4. 中间件
5. 异常处理

在本项目里对应：

- [main.py](/d:/data/code/MNMS/backend/app/main.py)
- [deps.py](/d:/data/code/MNMS/backend/app/api/deps.py)
- [jd.py](/d:/data/code/MNMS/backend/app/api/routers/jd.py)
- [interview.py](/d:/data/code/MNMS/backend/app/api/routers/interview.py)

你可以这样对照理解：

- Django `urls.py + views.py` -> FastAPI `router`
- Django serializer -> Pydantic schema
- Django middleware -> Starlette/FastAPI middleware

## 第二层：补 SQLAlchemy 2.0，而不是只看 ORM 语法

目标：理解数据库访问为什么变得更显式。

优先学习：

1. `Engine`
2. `Session` / `AsyncSession`
3. `select()`
4. `commit / rollback / refresh`
5. 模型映射

在本项目里对应：

- [database.py](/d:/data/code/MNMS/backend/app/core/database.py)
- [models.py](/d:/data/code/MNMS/backend/app/db/models.py)

重点认知：

- Django ORM 很多动作是帮你隐式做掉的
- SQLAlchemy 更接近“你自己明确掌控事务和会话”

## 第三层：补 PostgreSQL，不要只学 CRUD

目标：知道为什么团队会偏向 PostgreSQL。

优先学习：

1. 事务隔离级别
2. 索引基础
3. `JSONB`
4. 执行计划 `EXPLAIN`
5. 锁和并发写入

本项目里最值得观察的点：

- 结构化结果和任务状态用了 JSONB
- 多表关系更适合事务化处理

## 第四层：补消息队列，把 RabbitMQ 当成系统设计问题来学

目标：理解为什么不是所有逻辑都应该直接 HTTP 同步执行。

优先学习：

1. 什么是 broker / producer / consumer
2. queue / exchange / routing key 基础概念
3. ack / retry / dead-letter
4. 幂等性
5. 削峰填谷与解耦

在本项目里对应：

- [celery_app.py](/d:/data/code/MNMS/backend/app/core/celery_app.py)
- [queue.py](/d:/data/code/MNMS/backend/app/services/queue.py)
- [worker.py](/d:/data/code/MNMS/backend/app/tasks/worker.py)

## 第五层：把“高并发”理解成架构问题，不是框架标签

目标：避免以后面试或工作中只会说“FastAPI 更高并发”这种不够严谨的话。

你应该会解释：

1. 哪些请求是 I/O 密集型
2. 哪些请求必须异步拆出去
3. 为什么 Web worker 不能长期等外部 LLM
4. 为什么缓存只能缓解，不是万能药
5. 为什么数据库索引与事务设计也属于并发问题

## 第六层：安全性要补哪些

目标：从“能跑”走到“能上线”。

优先学习：

1. JWT 原理和常见坑
2. 密码哈希
3. CORS
4. 安全响应头
5. 输入校验和长度限制
6. 限流
7. 审计日志

在本项目里对应：

- [security.py](/d:/data/code/MNMS/backend/app/core/security.py)
- [middleware.py](/d:/data/code/MNMS/backend/app/core/middleware.py)
- [auth.py](/d:/data/code/MNMS/backend/app/api/routers/auth.py)

## 第七层：后续你可以自己继续补的能力

这部分没有全部塞进项目里，但工作里很常见。

- 监控：Prometheus / Grafana
- 日志：结构化日志、日志采样、链路 ID
- 任务重试：指数退避、死信队列
- 分布式追踪：OpenTelemetry
- 数据库优化：慢查询分析、连接池调优、分区
- 部署：CI/CD、蓝绿发布、滚动发布

## 最后给你一个最实用的阅读顺序

如果你时间紧，按下面顺序读项目：

1. [README.md](/d:/data/code/MNMS/README.md)
2. [REFACTOR_OVERVIEW_ZH.md](/d:/data/code/MNMS/docs/REFACTOR_OVERVIEW_ZH.md)
3. [main.py](/d:/data/code/MNMS/backend/app/main.py)
4. [models.py](/d:/data/code/MNMS/backend/app/db/models.py)
5. [worker.py](/d:/data/code/MNMS/backend/app/tasks/worker.py)
6. [HIGH_CONCURRENCY_GUIDE_ZH.md](/d:/data/code/MNMS/docs/HIGH_CONCURRENCY_GUIDE_ZH.md)

这样你会先知道“系统长什么样”，再去理解“为什么要这么长”。
