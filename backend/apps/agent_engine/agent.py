from __future__ import annotations

from apps.agent_engine.skills.jd_analyzer import JDAnalyzerSkill
from apps.agent_engine.skills.mock_interviewer import MockInterviewerSkill
from apps.agent_engine.skills.resume_optimizer import ResumeOptimizerSkill
from apps.agent_engine.tools.llm_client import LLMClient
from apps.agent_engine.tools.rag_store import RAGStore


class PhoenixAgent:
    """Project Phoenix 主 Agent：统一编排 JD 分析、简历优化、模拟面试三类能力。"""
    # 大模型相关能力：RAG\LLM被下沉成基础设施，包装在agent——engine/tools里面。
    # 这样后续想要修改LLM或者调整RAG模型，就方便一些
    def __init__(self) -> None:
        llm = LLMClient()
        rag = RAGStore.get_instance()
        self.jd_analyzer = JDAnalyzerSkill(llm=llm)
        self.resume_optimizer = ResumeOptimizerSkill(llm=llm)
        self.mock_interviewer = MockInterviewerSkill(llm=llm, rag=rag)

    # 下面四个函数主要作用是暴露接口，实际处理问题的SKILL。
    def analyze_jd(self, jd_text: str) -> dict:
        """分析岗位"""
        return self.jd_analyzer.run(jd_text)

    def optimize_resume(self, jd_analysis: dict, resume_text: str) -> dict:
        """优化简历"""
        return self.resume_optimizer.run(jd_analysis, resume_text)

    def start_interview(self, topic: str, history: list[dict] | None = None) -> dict:
        """开始面试"""
        _ = history
        return self.mock_interviewer.start(topic)

    def continue_interview(self, topic: str, user_answer: str, history: list[dict]) -> dict:
        """继续面试"""
        return self.mock_interviewer.continue_chat(topic=topic, user_answer=user_answer, history=history)