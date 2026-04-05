from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.db.models import JobType, User
from app.schemas.jd import JDAnalyzeRequest
from app.schemas.job import JobSubmittedResponse
from app.services.jobs import create_job, to_submitted_response
from app.services.queue import dispatch_job
from app.tasks.worker import process_jd_analysis

router = APIRouter(prefix="/jd", tags=["jd"])


@router.post("/analyze", response_model=JobSubmittedResponse)
async def analyze_jd(
    payload: JDAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobSubmittedResponse:
    job = await create_job(
        session,
        user_id=current_user.id,
        job_type=JobType.JD_ANALYZE,
        request_payload=payload.model_dump(),
    )
    # REFACTOR: 这里不再让 Web 进程执行 LLM 调用，而是立即投递到 RabbitMQ。
    await dispatch_job(session, job, process_jd_analysis, str(job.id), current_user.id, payload.jd_text)
    return to_submitted_response(job)
