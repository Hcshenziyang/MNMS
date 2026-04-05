import pytest
from pydantic import ValidationError

from app.schemas.interview import InterviewChatRequest


def test_interview_start_requires_topic():
    payload = InterviewChatRequest(topic="Python后端")

    assert payload.topic == "Python后端"
    assert payload.session_id is None


def test_interview_continue_requires_answer():
    with pytest.raises(ValidationError):
        InterviewChatRequest(session_id=1)
