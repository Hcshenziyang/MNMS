from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeOptimizeRequest(BaseModel):
    session_id: int = Field(ge=1)
    resume_text: str = Field(min_length=10, max_length=12000)
