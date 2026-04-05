from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.db.models import JobStatus, JobType


class JobSubmittedResponse(BaseModel):
    job_id: UUID
    job_type: JobType
    status: JobStatus
    submitted_at: datetime


class JobRead(BaseModel):
    job_id: UUID
    job_type: JobType
    status: JobStatus
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    session_id: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
