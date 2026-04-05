from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionKind(str, Enum):
    JD = "jd"
    RESUME = "resume"
    INTERVIEW = "interview"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AnalysisSourceType(str, Enum):
    JD = "jd"
    RESUME = "resume"


class JobType(str, Enum):
    JD_ANALYZE = "jd_analyze"
    RESUME_OPTIMIZE = "resume_optimize"
    INTERVIEW_START = "interview_start"
    INTERVIEW_CONTINUE = "interview_continue"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["JobRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user_kind_created", "user_id", "session_kind", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(255))
    session_kind: Mapped[SessionKind] = mapped_column(SqlEnum(SessionKind, name="session_kind"))

    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="session")
    jobs: Mapped[list["JobRecord"]] = relationship(back_populates="session")


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole] = mapped_column(SqlEnum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class AnalysisResult(TimestampMixin, Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index("ix_analysis_results_user_source_created", "user_id", "source_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)
    source_type: Mapped[AnalysisSourceType] = mapped_column(SqlEnum(AnalysisSourceType, name="analysis_source_type"))
    source_text: Mapped[str] = mapped_column(Text)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSONB)

    user: Mapped[User] = relationship(back_populates="analysis_results")
    session: Mapped[ChatSession | None] = relationship(back_populates="analyses")


class JobRecord(Base):
    __tablename__ = "job_records"
    __table_args__ = (
        Index("ix_job_records_user_status_created", "user_id", "status", "created_at"),
        Index("ix_job_records_session_created", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)
    job_type: Mapped[JobType] = mapped_column(SqlEnum(JobType, name="job_type"), index=True)
    status: Mapped[JobStatus] = mapped_column(SqlEnum(JobStatus, name="job_status"), default=JobStatus.QUEUED)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="jobs")
    session: Mapped[ChatSession | None] = relationship(back_populates="jobs")
