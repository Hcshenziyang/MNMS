from __future__ import annotations

from apps.agent_engine.tools.llm_client import LLMClient
from apps.agent_engine.tools.text_tools import compute_match_score


class ResumeOptimizerSkill:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def run(self, jd_analysis: dict, resume_text: str) -> dict:
        jd_keywords = jd_analysis.get("jd_keywords", []) if isinstance(jd_analysis, dict) else []
        matched, missing, score = compute_match_score(jd_keywords, resume_text)

        prompt = (
            "你是资深技术招聘顾问。请基于岗位关键字和候选人简历给出优化建议。\n"
            "输出结构：\n"
            "1) 总体匹配度评估\n"
            "2) 需要补强的项目经历（至少3条）\n"
            "3) 可直接替换到简历中的措辞示例（至少5条，量化表达）\n"
            "4) 面试时可主动强调的亮点（3条）\n\n"
            f"岗位关键词：{', '.join(jd_keywords)}\n"
            f"已匹配关键词：{', '.join(matched) if matched else '无'}\n"
            f"待补关键词：{', '.join(missing) if missing else '无'}\n\n"
            f"简历内容：\n{resume_text}"
        )
        content = self.llm.generate(prompt, temperature=0.25)

        metadata = {
            "jd_keywords": jd_keywords,
            "matched_keywords": matched,
            "missing_keywords": missing,
            "match_score": score,
        }
        return {"content": content, "metadata": metadata}