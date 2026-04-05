from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import desc, select

from app.agent_engine.agent import PhoenixAgent
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.db.models import (
    AnalysisResult,
    AnalysisSourceType,
    ChatMessage,
    ChatSession,
    JobRecord,
    JobStatus,
    MessageRole,
    SessionKind,
)
from app.services.cache import cache_service

logger = get_task_logger(__name__)
agent = PhoenixAgent()


def _message_payload(message: ChatMessage) -> dict:
    return {
        "role": message.role.value,
        "content": message.content,
        "metadata": message.meta or {},
    }


def _cache_recent_session_messages(session_id: int) -> None:
    with SyncSessionLocal() as db:
        result = db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(10)
        )
        recent_messages = list(reversed(result.scalars().all()))
        payload = [_message_payload(message) for message in recent_messages]
        cache_service.set_json(f"session:{session_id}:recent", payload, ttl=settings.session_cache_seconds)


def _load_job(db, job_id: str) -> JobRecord:
    job = db.get(JobRecord, UUID(job_id))
    if job is None:
        raise RuntimeError(f"job {job_id} not found")
    return job


def _mark_running(db, job: JobRecord) -> None:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    db.commit()


def _mark_failed(db, job: JobRecord, exc: Exception) -> None:
    job.status = JobStatus.FAILED
    job.error_message = str(exc)
    job.retry_count += 1
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def _mark_succeeded(db, job: JobRecord, result_payload: dict, session_id: int | None) -> None:
    job.status = JobStatus.SUCCEEDED
    job.result_payload = result_payload
    job.session_id = session_id
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


@celery_app.task(name="phoenix.process_jd_analysis")
def process_jd_analysis(job_id: str, user_id: int, jd_text: str) -> None:
    with SyncSessionLocal() as db:
        job = _load_job(db, job_id)
        _mark_running(db, job)
        try:
            result = agent.analyze_jd(jd_text)
            session_obj = ChatSession(user_id=user_id, topic="岗位分析", session_kind=SessionKind.JD)
            db.add(session_obj)
            db.flush()

            db.add(ChatMessage(session_id=session_obj.id, role=MessageRole.USER, content=jd_text, meta={}))
            assistant_message = ChatMessage(
                session_id=session_obj.id,
                role=MessageRole.ASSISTANT,
                content=result["content"],
                meta=result.get("metadata", {}),
            )
            db.add(assistant_message)
            db.add(
                AnalysisResult(
                    user_id=user_id,
                    session_id=session_obj.id,
                    source_type=AnalysisSourceType.JD,
                    source_text=jd_text,
                    structured_data=result.get("metadata", {}),
                )
            )
            db.commit()
            db.refresh(assistant_message)

            payload = {
                "session_id": session_obj.id,
                "message": _message_payload(assistant_message),
            }
            _mark_succeeded(db, job, payload, session_obj.id)
            _cache_recent_session_messages(session_obj.id)
        except Exception as exc:
            logger.exception("JD analysis failed: %s", exc)
            db.rollback()
            _mark_failed(db, job, exc)


@celery_app.task(name="phoenix.process_resume_optimization")
def process_resume_optimization(job_id: str, user_id: int, session_id: int, resume_text: str) -> None:
    with SyncSessionLocal() as db:
        job = _load_job(db, job_id)
        _mark_running(db, job)
        try:
            latest_jd_result = db.execute(
                select(AnalysisResult)
                .where(
                    AnalysisResult.user_id == user_id,
                    AnalysisResult.source_type == AnalysisSourceType.JD,
                )
                .order_by(desc(AnalysisResult.created_at))
                .limit(1)
            ).scalar_one_or_none()
            if latest_jd_result is None:
                raise RuntimeError("请先完成一次岗位分析后再进行简历优化。")

            db.add(ChatMessage(session_id=session_id, role=MessageRole.USER, content=resume_text, meta={}))
            result = agent.optimize_resume(
                jd_analysis=latest_jd_result.structured_data,
                resume_text=resume_text,
            )
            assistant_message = ChatMessage(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=result["content"],
                meta=result.get("metadata", {}),
            )
            db.add(assistant_message)
            db.add(
                AnalysisResult(
                    user_id=user_id,
                    session_id=session_id,
                    source_type=AnalysisSourceType.RESUME,
                    source_text=resume_text,
                    structured_data=result.get("metadata", {}),
                )
            )
            db.commit()
            db.refresh(assistant_message)

            payload = {
                "session_id": session_id,
                "message": _message_payload(assistant_message),
            }
            _mark_succeeded(db, job, payload, session_id)
            _cache_recent_session_messages(session_id)
        except Exception as exc:
            logger.exception("Resume optimization failed: %s", exc)
            db.rollback()
            _mark_failed(db, job, exc)


@celery_app.task(name="phoenix.process_interview_start")
def process_interview_start(job_id: str, user_id: int, topic: str | None) -> None:
    actual_topic = topic or "Python后端"
    with SyncSessionLocal() as db:
        job = _load_job(db, job_id)
        _mark_running(db, job)
        try:
            result = agent.start_interview(topic=actual_topic, history=[])
            session_obj = ChatSession(
                user_id=user_id,
                topic=f"模拟面试-{actual_topic}",
                session_kind=SessionKind.INTERVIEW,
            )
            db.add(session_obj)
            db.flush()

            assistant_message = ChatMessage(
                session_id=session_obj.id,
                role=MessageRole.ASSISTANT,
                content=result["content"],
                meta=result.get("metadata", {}),
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            payload = {
                "session_id": session_obj.id,
                "message": _message_payload(assistant_message),
            }
            _mark_succeeded(db, job, payload, session_obj.id)
            _cache_recent_session_messages(session_obj.id)
        except Exception as exc:
            logger.exception("Interview start failed: %s", exc)
            db.rollback()
            _mark_failed(db, job, exc)


@celery_app.task(name="phoenix.process_interview_continue")
def process_interview_continue(job_id: str, user_id: int, session_id: int, user_answer: str | None) -> None:
    if not user_answer:
        raise RuntimeError("继续对话时必须提供 user_answer。")

    with SyncSessionLocal() as db:
        job = _load_job(db, job_id)
        _mark_running(db, job)
        try:
            session_obj = db.execute(
                select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            ).scalar_one_or_none()
            if session_obj is None:
                raise RuntimeError("会话不存在。")

            db.add(ChatMessage(session_id=session_id, role=MessageRole.USER, content=user_answer, meta={}))
            db.flush()

            history_messages = db.execute(
                select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
            ).scalars().all()
            history = [_message_payload(message) for message in history_messages]

            result = agent.continue_interview(
                topic=session_obj.topic.replace("模拟面试-", "", 1),
                user_answer=user_answer,
                history=history,
            )
            assistant_message = ChatMessage(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=result["content"],
                meta=result.get("metadata", {}),
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            payload = {
                "session_id": session_id,
                "message": _message_payload(assistant_message),
            }
            _mark_succeeded(db, job, payload, session_id)
            _cache_recent_session_messages(session_id)
        except Exception as exc:
            logger.exception("Interview continue failed: %s", exc)
            db.rollback()
            _mark_failed(db, job, exc)
