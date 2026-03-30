from __future__ import annotations

import re
from dataclasses import asdict

from django.conf import settings
from django.core.cache import cache

from apps.agent_engine.tools.llm_client import LLMClient
from apps.agent_engine.tools.rag_store import QuestionDoc, RAGStore


class MockInterviewerSkill:
    """面试功能实际执行类"""
    def __init__(self, llm: LLMClient | None = None, rag: RAGStore | None = None) -> None:
        self.llm = llm or LLMClient()  # 底层能力：大模型调用客户端
        self.rag = rag or RAGStore.get_instance()  # 底层能力：数据库检索

    @staticmethod
    def _topic_cache_key(topic: str) -> str:
        """缓存key规范化处理，转小写+非中英文字符替换-。示例：【rag:topic:python后端】"""
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", topic.lower()).strip("-")
        return f"rag:topic:{normalized or 'default'}"

    def _question_pool(self, topic: str) -> list[QuestionDoc]:
        """题池，检索缓存、保存缓存"""
        key = self._topic_cache_key(topic)  # 根据topic生成key
        cached = cache.get(key)  # 去Redis里找对应的key
        if cached:  # 如果命中就把缓存里题库字典还原成QuestionDoc对象列表。
            return [QuestionDoc(**item) for item in cached]

        docs = self.rag.questions_for_topic(topic, top_k=settings.RAG_TOP_K)  # 如果没有命中，就做真实检索
        cache.set(key, [asdict(doc) for doc in docs], timeout=settings.RAG_CACHE_SECONDS)  # 保存缓存
        return docs

    def _build_interview_summary_context(self, history: list[dict], max_chars: int = 4000) -> str:
        """
        从历史消息中提取适合做阶段总结的上下文。
        只保留user回答和assistant的点评/追问，按轮次压缩。
        这里先用字符数做粗粒度限制，后续可替换成更精确的 token 计数。
        """
        lines = []
        round_no = 0

        for msg in history:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                round_no += 1
                # 用户回答过长时先截断
                shortened = content[:300]
                lines.append(f"第{round_no}轮-候选人回答：{shortened}")
            elif role == "assistant":
                # assistant 内容里可能同时包含点评和下一题，这里也做截断
                shortened = content[:300]
                lines.append(f"第{round_no}轮-面试官反馈：{shortened}")
        # 从后往前保留，优先保最近轮次
        result = []
        total = 0
        for line in reversed(lines):
            if total + len(line) > max_chars:
                break
            result.append(line)
            total += len(line)
        return "\n".join(reversed(result))

    def start(self, topic: str) -> dict:
        pool = self._question_pool(topic)
        if not pool:  # 没有题池时候，给一个通用的介绍。
            opening = f"我们开始 {topic} 模拟面试。请先介绍一个你做过的后端项目，并说明你的技术职责。"
            return {
                "content": opening,
                "metadata": {"source": "fallback", "topic": topic, "question_pool": []},
            }

        first = pool[0]
        content = (
            f"我们开始 {topic} 模拟面试。\n"
            f"第 1 题：{first.question}\n"
            "你可以先给出思路，再补充具体工程实践。"
        )
        metadata = {
            "source": "retrieved_and_generated",
            "topic": topic,
            "question_pool": [doc.question for doc in pool],
            "current_question_index": 0,
        }
        return {"content": content, "metadata": metadata}

    def continue_chat(self, topic: str, user_answer: str, history: list[dict]) -> dict:
        pool = self._question_pool(topic)
        if not pool:
            fallback = self.llm.generate(  # 题池不存在，调用LLM
                f"请点评候选人这段回答并追问一个问题：\n{user_answer}",
                temperature=0.3,
            )
            return {"content": fallback, "metadata": {"source": "fallback", "topic": topic}}

        # 如果题池存在，则顺着题池往下，半约束型，LLM仅作点评和优化辅助。
        user_count = len([m for m in history if m.get("role") == "user"])  # 基于历史对话次数推断题池位置
        current_index = min(max(user_count - 1, 0), len(pool) - 1)
        next_index = min(user_count, len(pool) - 1)

        current_question = pool[current_index].question
        next_question = pool[next_index].question

        prompt = (
            "你是严格但友好的技术面试官。请对候选人的回答进行简洁点评（优点1条+改进2条），"
            "然后给出下一道追问题。\n"
            f"面试主题：{topic}\n"
            f"当前题目：{current_question}\n"
            f"候选人回答：{user_answer}\n"
            f"下一题候选池：{next_question}"
        )
        feedback = self.llm.generate(prompt, temperature=0.35)
        if user_count >= len(pool):  # 判断题池是否结束
            summary_context = self._build_interview_summary_context(history, max_chars=4000)
            final_prompt = (
                "你是一名技术面试官，请基于以下完整面试过程给出阶段总结。\n"
                "输出格式：\n"
                "1. 优势 3 条\n"
                "2. 风险 3 条\n"
                "3. 补强建议 3 条\n\n"
                f"面试主题：{topic}\n"
                f"面试过程：\n{summary_context}"
            )
            final_summary = self.llm.generate(final_prompt, temperature=0.2)
            content = f"{feedback}\n\n本轮题库已完成，阶段总结如下：\n{final_summary}"
        else:
            content = f"{feedback}\n\n下一题：{next_question}"

        metadata = {
            "source": "retrieved_and_generated",
            "topic": topic,
            "current_question_index": next_index,
            "question_pool": [doc.question for doc in pool],
        }
        return {"content": content, "metadata": metadata}