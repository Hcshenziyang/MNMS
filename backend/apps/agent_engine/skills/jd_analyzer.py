from __future__ import annotations

from apps.agent_engine.tools.llm_client import LLMClient
from apps.agent_engine.tools.text_tools import extract_keywords, pick_lines


class JDAnalyzerSkill:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def run(self, jd_text: str) -> dict:
        keywords = extract_keywords(jd_text, top_n=12)
        responsibilities = pick_lines(jd_text, hints=["负责", "职责", "responsible"], limit=6)  # 职责
        requirements = pick_lines(jd_text, hints=["要求", "熟悉", "掌握", "require", "must"], limit=8)  # 必须
        preferred = pick_lines(jd_text, hints=["加分", "优先", "plus", "nice to have"], limit=5)  # 加分

        prompt = (
            "请基于以下岗位描述，输出中文分析结果，结构如下：\n"
            "1) 岗位核心能力（3-5条）\n"
            "2) 面试高频考点（3-5条）\n"
            "3) 候选人准备建议（3条）\n\n"
            f"岗位描述：\n{jd_text}\n\n"
            f"已提取关键词：{', '.join(keywords)}"  # 提供一个引导锚点
        )
        content = self.llm.generate(prompt, temperature=0.2)

        metadata = {
            "jd_keywords": keywords,
            "must_have_skills": requirements,
            "nice_to_have_skills": preferred,
            "responsibilities": responsibilities,
        }
        return {"content": content, "metadata": metadata}  # metadata来源于规则处理