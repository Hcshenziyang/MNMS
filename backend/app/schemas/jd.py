from __future__ import annotations

from pydantic import BaseModel, Field


class JDAnalyzeRequest(BaseModel):
    jd_text: str = Field(min_length=10, max_length=12000)
