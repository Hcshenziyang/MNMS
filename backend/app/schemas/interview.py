from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class InterviewChatRequest(BaseModel):
    topic: str | None = Field(default=None, min_length=2, max_length=120)
    session_id: int | None = Field(default=None, ge=1)
    user_answer: str | None = Field(default=None, min_length=2, max_length=6000)

    @model_validator(mode="after")
    def validate_payload(self) -> "InterviewChatRequest":
        if self.session_id and self.topic:
            raise ValueError("session_id 和 topic 不能同时提供。")
        if not self.session_id and not self.topic:
            raise ValueError("开始面试时必须提供 topic，或继续对话时提供 session_id。")
        if self.session_id and not self.user_answer:
            raise ValueError("继续对话时必须提供 user_answer。")
        return self
