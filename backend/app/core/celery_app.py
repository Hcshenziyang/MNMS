from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "phoenix",
    broker=settings.rabbitmq_url,
    include=["app.tasks.worker"],
)

celery_app.conf.update(
    task_default_queue="phoenix.ai",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_ignore_result=True,
    broker_heartbeat=30,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
)
