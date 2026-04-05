from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.db.models import AnalysisResult, AnalysisSourceType, ChatSession, JobType, User
from app.schemas.job import JobSubmittedResponse
from app.schemas.resume import ResumeOptimizeRequest
from app.services.jobs import create_job, to_submitted_response
from app.services.queue import dispatch_job
from app.tasks.worker import process_resume_optimization

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/optimize", response_model=JobSubmittedResponse)
async def optimize_resume(
    payload: ResumeOptimizeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobSubmittedResponse:
    session_result = await session.execute(
        select(ChatSession).where(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
    )
    target_session = session_result.scalar_one_or_none()
    if target_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")

    latest_jd = await session.execute(
        select(AnalysisResult)
        .where(
            AnalysisResult.user_id == current_user.id,
            AnalysisResult.source_type == AnalysisSourceType.JD,
        )
        .order_by(desc(AnalysisResult.created_at))
        .limit(1)
    )
    if latest_jd.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先完成一次岗位分析。")

    job = await create_job(
        session,
        user_id=current_user.id,
        session_id=payload.session_id,
        job_type=JobType.RESUME_OPTIMIZE,
        request_payload=payload.model_dump(),
    )
    await dispatch_job(
        session,
        job,
        process_resume_optimization,
        str(job.id),
        current_user.id,
        payload.session_id,
        payload.resume_text,
    )
    return to_submitted_response(job)
