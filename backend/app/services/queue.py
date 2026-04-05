from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRecord, JobStatus


async def dispatch_job(
    session: AsyncSession,
    job: JobRecord,
    task_callable,
    *task_args,
) -> None:
    try:
        task_callable.delay(*task_args)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = f"任务投递失败: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RabbitMQ 不可用，任务未成功投递。",
        ) from exc
