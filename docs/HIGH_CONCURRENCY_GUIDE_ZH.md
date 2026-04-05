# 为什么是 FastAPI + PostgreSQL + RabbitMQ

你提到这个组合“可能是为了更高并发准备的”，这个方向是对的，但要说严谨一点：

- `FastAPI` 本身不等于高并发
- `PostgreSQL` 本身也不等于高并发
- `RabbitMQ` 也不是加上就一定更快

真正提升的是整条链路的承压方式。

## 1. 旧版本为什么扛不住慢请求

旧链路大致是：

1. 浏览器发请求
2. Django 视图直接做参数校验
3. 视图里直接调 Agent / LLM / RAG
4. Web worker 一直阻塞，直到结果返回

这会带来几个问题：

- 一个慢请求会长期占住一个 Web worker
- LLM API 抖动时，请求排队会越来越严重
- 面试对话、岗位分析、简历优化都属于“高耗时请求”，它们和健康检查、登录请求争抢同一批 Web 进程
- 一旦并发上来，吞吐会先被“等待外部服务”拖垮，而不是 CPU 先打满

## 2. 新版本怎么拆压

### FastAPI 层

在 [jd.py](/d:/data/code/MNMS/backend/app/api/routers/jd.py) 里你会看到，接口现在只做三件事：

1. 校验请求
2. 创建数据库任务记录
3. 投递到 RabbitMQ

这意味着：

- Web 层不再直接承受 LLM 的长等待
- 登录、健康检查、任务查询这些轻请求不会被慢任务拖死
- Web 层更适合横向扩容

### RabbitMQ 层

RabbitMQ 的作用不是“让任务 magically 更快”，而是：

- 削峰填谷
- 解耦 Web 和慢任务
- 给任务执行增加缓冲区

对应代码：

- [celery_app.py](/d:/data/code/MNMS/backend/app/core/celery_app.py)
- [queue.py](/d:/data/code/MNMS/backend/app/services/queue.py)

这里还专门做了几个并发相关配置：

- `worker_prefetch_multiplier=1`
  作用：避免某个 Celery worker 一次性抢走太多任务，提升公平性。
- `task_acks_late=True`
  作用：任务完成后才确认，worker 异常退出时任务更容易被重新投递。
- `task_reject_on_worker_lost=True`
  作用：worker 意外挂掉时，减少“任务丢了但系统以为成功”的风险。

### Celery Worker 层

真正慢的工作现在在 [worker.py](/d:/data/code/MNMS/backend/app/tasks/worker.py)：

- LLM 调用
- RAG 检索
- 结果入库
- 会话缓存刷新

这样做的好处是：

- Web 进程保持轻量
- Worker 数量可以单独调整
- 如果后续某个任务特别重，可以拆独立队列，而不是影响整个 API 服务

## 3. PostgreSQL 为什么比 MySQL 更适合这一版

注意，这里不是说 MySQL 不行，而是 PostgreSQL 更适合这套新架构继续往下长。

### PostgreSQL 更适合的点

- `JSONB`：本项目里 `metadata`、`structured_data`、`job result payload` 都是结构化 JSON
- 事务能力稳定：任务状态、消息写入、分析结果入库更适合放在清晰事务里
- 生态成熟：和 SQLAlchemy、Alembic 的配合很顺
- 后续扩展空间大：全文检索、复杂查询、分区、逻辑复制、物化视图等都更方便

对应模型：

- [models.py](/d:/data/code/MNMS/backend/app/db/models.py)

你会看到这些字段都很适合 PostgreSQL：

- `chat_messages.metadata`
- `analysis_results.structured_data`
- `job_records.request_payload`
- `job_records.result_payload`

## 4. 高并发到底解决在哪些地方

这个问题你要求单独解释，我直接按“问题 -> 解决位置”列出来。

### 问题 1：慢 LLM 请求拖住 Web 进程

解决位置：

- [jd.py](/d:/data/code/MNMS/backend/app/api/routers/jd.py)
- [resume.py](/d:/data/code/MNMS/backend/app/api/routers/resume.py)
- [interview.py](/d:/data/code/MNMS/backend/app/api/routers/interview.py)
- [worker.py](/d:/data/code/MNMS/backend/app/tasks/worker.py)

做法：

- 路由只投递任务，不做重活
- 真正耗时操作移到 Celery worker

### 问题 2：高峰时请求直接打爆后端

解决位置：

- [celery_app.py](/d:/data/code/MNMS/backend/app/core/celery_app.py)
- `docker-compose.yml`

做法：

- RabbitMQ 充当缓冲层
- Worker 数量可独立扩容

### 问题 3：频繁重复的上下文、LLM 结果、题池检索浪费资源

解决位置：

- [cache.py](/d:/data/code/MNMS/backend/app/services/cache.py)
- [llm_client.py](/d:/data/code/MNMS/backend/app/agent_engine/tools/llm_client.py)
- [mock_interviewer.py](/d:/data/code/MNMS/backend/app/agent_engine/skills/mock_interviewer.py)

做法：

- LLM 响应缓存
- RAG 题池缓存
- 会话最近消息缓存

### 问题 4：任务状态不透明，前端只能一直等 HTTP 连接

解决位置：

- [job.py](/d:/data/code/MNMS/backend/app/schemas/job.py)
- [jobs.py](/d:/data/code/MNMS/backend/app/api/routers/jobs.py)
- [App.vue](/d:/data/code/MNMS/frontend/src/App.vue)

做法：

- 建 `job_records` 表
- 接口先返回 `job_id`
- 前端轮询任务状态

这不是“更快”，但它让系统在高并发下更稳。

## 5. 这一版还没有解决的高并发问题

工程上要严谨，这里必须告诉你哪些还没做。

- 还没有做限流
- 还没有做任务优先级和多队列拆分
- 还没有做 PostgreSQL 读写分离
- 还没有做 RabbitMQ 死信队列
- 还没有做完整的监控告警
- 还没有做分布式追踪

所以这版更准确地说是：

“已经具备面向更高并发继续演进的工程骨架”

而不是：

“已经做成超大规模高并发系统”

## 6. 你可以怎么理解这套组合

一个更接近真实工作的理解方式是：

- FastAPI：负责快速、安全地接住请求
- PostgreSQL：负责可靠地存状态
- Redis：负责减少重复计算和热点读取
- RabbitMQ：负责把慢任务和入口流量解耦
- Celery Worker：负责执行慢任务

这五个组件配在一起，解决的是“系统怎么稳”，不是单点组件跑分。
