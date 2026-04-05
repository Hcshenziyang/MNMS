from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.db.models import ChatSession, JobType, User
from app.schemas.interview import InterviewChatRequest
from app.schemas.job import JobSubmittedResponse
from app.services.jobs import create_job, to_submitted_response
from app.services.queue import dispatch_job
from app.tasks.worker import process_interview_continue, process_interview_start

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("/chat", response_model=JobSubmittedResponse)
async def interview_chat(
    payload: InterviewChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobSubmittedResponse:
    if payload.session_id:
        result = await session.execute(
            select(ChatSession).where(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
        )
        target_session = result.scalar_one_or_none()
        if target_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")

        job = await create_job(
            session,
            user_id=current_user.id,
            session_id=payload.session_id,
            job_type=JobType.INTERVIEW_CONTINUE,
            request_payload=payload.model_dump(),
        )
        await dispatch_job(
            session,
            job,
            process_interview_continue,
            str(job.id),
            current_user.id,
            payload.session_id,
            payload.user_answer,
        )
        return to_submitted_response(job)

    job = await create_job(
        session,
        user_id=current_user.id,
        job_type=JobType.INTERVIEW_START,
        request_payload=payload.model_dump(),
    )
    await dispatch_job(session, job, process_interview_start, str(job.id), current_user.id, payload.topic)
    return to_submitted_response(job)
