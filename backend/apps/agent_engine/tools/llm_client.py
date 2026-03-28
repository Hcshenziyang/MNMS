from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    model: str
    api_key: str
    base_url: str | None = None


class LLMClient:
    def __init__(self) -> None:
        self._client = None
        self._config = self._resolve_config()

    @staticmethod
    def _resolve_config() -> LLMConfig:
        provider = settings.LLM_PROVIDER.lower()
        if provider == "deepseek":
            return LLMConfig(
                model=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        return LLMConfig(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or None,
        )

    def available(self) -> bool:
        return bool(self._config.api_key and OpenAI is not None)

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.available():
            return None
        self._client = OpenAI(api_key=self._config.api_key, base_url=self._config.base_url)
        return self._client

    @staticmethod
    def _cache_key(system_prompt: str, prompt: str, temperature: float, max_tokens: int, model: str) -> str:
        source = json.dumps(
            {
                "system": system_prompt,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "model": model,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return f"llm:{hashlib.sha256(source.encode('utf-8')).hexdigest()}"

    def _fallback_response(self, prompt: str) -> str:
        snippet = prompt.strip().replace("\n", " ")[:220]
        if not snippet:
            return "当前未配置可用的大模型 Key，请稍后重试。"
        return (
            "当前运行在离线回退模式（未检测到可用 LLM API Key）。"
            "以下给出规则化建议：\n"
            f"- 核心输入摘要：{snippet}\n"
            "- 建议你补充可量化成果、关键技术栈和业务价值。"
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "你是资深技术面试官与职业发展顾问。",
        temperature: float = 0.3,
        max_tokens: int = 800,
        cache_ttl: int | None = None,
    ) -> str:
        cache_ttl = cache_ttl or settings.LLM_CACHE_SECONDS
        cache_key = self._cache_key(system_prompt, prompt, temperature, max_tokens, self._config.model)

        cached = cache.get(cache_key)
        if cached:
            return cached

        client = self._get_client()
        if client is None:
            fallback = self._fallback_response(prompt)
            cache.set(cache_key, fallback, timeout=cache_ttl)
            return fallback

        try:
            response = client.chat.completions.create(
                model=self._config.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                content = "模型返回为空，请稍后再试。"
            cache.set(cache_key, content, timeout=cache_ttl)
            return content
        except Exception as exc:  # pragma: no cover
            logger.exception("LLM call failed: %s", exc)
            fallback = self._fallback_response(prompt)
            cache.set(cache_key, fallback, timeout=cache_ttl)
            return fallback