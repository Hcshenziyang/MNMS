from __future__ import annotations

from app.agent_engine.skills.jd_analyzer import JDAnalyzerSkill
from app.agent_engine.skills.mock_interviewer import MockInterviewerSkill
from app.agent_engine.skills.resume_optimizer import ResumeOptimizerSkill
from app.agent_engine.tools.llm_client import LLMClient
from app.agent_engine.tools.rag_store import RAGStore


class PhoenixAgent:
    """统一编排 JD 分析、简历优化和模拟面试能力。"""

    def __init__(self) -> None:
        llm = LLMClient()
        rag = RAGStore.get_instance()
        self.jd_analyzer = JDAnalyzerSkill(llm=llm)
        self.resume_optimizer = ResumeOptimizerSkill(llm=llm)
        self.mock_interviewer = MockInterviewerSkill(llm=llm, rag=rag)

    def analyze_jd(self, jd_text: str) -> dict:
        return self.jd_analyzer.run(jd_text)

    def optimize_resume(self, jd_analysis: dict, resume_text: str) -> dict:
        return self.resume_optimizer.run(jd_analysis, resume_text)

    def start_interview(self, topic: str, history: list[dict] | None = None) -> dict:
        _ = history
        return self.mock_interviewer.start(topic)

    def continue_interview(self, topic: str, user_answer: str, history: list[dict]) -> dict:
        return self.mock_interviewer.continue_chat(topic=topic, user_answer=user_answer, history=history)
