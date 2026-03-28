from __future__ import annotations

import re
from dataclasses import asdict

from django.conf import settings
from django.core.cache import cache

from apps.agent_engine.tools.llm_client import LLMClient
from apps.agent_engine.tools.rag_store import QuestionDoc, RAGStore


class MockInterviewerSkill:
    def __init__(self, llm: LLMClient | None = None, rag: RAGStore | None = None) -> None:
        self.llm = llm or LLMClient()
        self.rag = rag or RAGStore.get_instance()

    @staticmethod
    def _topic_cache_key(topic: str) -> str:
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", topic.lower()).strip("-")
        return f"rag:topic:{normalized or 'default'}"

    def _question_pool(self, topic: str) -> list[QuestionDoc]:
        key = self._topic_cache_key(topic)
        cached = cache.get(key)
        if cached:
            return [QuestionDoc(**item) for item in cached]

        docs = self.rag.questions_for_topic(topic, top_k=settings.RAG_TOP_K)
        cache.set(key, [asdict(doc) for doc in docs], timeout=settings.RAG_CACHE_SECONDS)
        return docs

    def start(self, topic: str) -> dict:
        pool = self._question_pool(topic)
        if not pool:
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
            fallback = self.llm.generate(
                f"请点评候选人这段回答并追问一个问题：\n{user_answer}",
                temperature=0.3,
            )
            return {"content": fallback, "metadata": {"source": "fallback", "topic": topic}}

        user_count = len([m for m in history if m.get("role") == "user"])
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

        if user_count >= len(pool):
            final_prompt = (
                f"请基于以下回答给出最终总结（优势/风险/补强建议各3条）：\n{user_answer}"
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