from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRecord, JobStatus, JobType
from app.schemas.job import JobRead, JobSubmittedResponse


async def create_job(
    session: AsyncSession,
    *,
    user_id: int,
    job_type: JobType,
    request_payload: dict,
    session_id: int | None = None,
) -> JobRecord:
    job = JobRecord(
        user_id=user_id,
        session_id=session_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        request_payload=request_payload,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def to_submitted_response(job: JobRecord) -> JobSubmittedResponse:
    return JobSubmittedResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        submitted_at=job.created_at,
    )


def to_job_read(job: JobRecord) -> JobRead:
    return JobRead(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        submitted_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        session_id=job.session_id,
        result=job.result_payload,
        error=job.error_message,
    )
