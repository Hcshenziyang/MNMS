# 大模型调用封装层：模型配置解析、客户端懒加载、基于prompt的缓存、调用失败/未配置时降级回退
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
        """
        大模型配置。支持DEEPSEEK和openai的风格接口。
        """
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
        """检查大模型配置是否可用。同时满足有API以及OPENAI SDK正确安装"""
        return bool(self._config.api_key and OpenAI is not None)

    def _get_client(self):
        """
        懒加载大模型。第一次调用时候才会创建SDK client，后续复用一个实例，减少初始化开销。
        """
        if self._client is not None:
            return self._client
        if not self.available():
            return None
        self._client = OpenAI(api_key=self._config.api_key, base_url=self._config.base_url)
        return self._client

    @staticmethod
    def _cache_key(system_prompt: str, prompt: str, temperature: float, max_tokens: int, model: str) -> str:
        """
        LLM请求缓存。缓存key包含不仅包含了prompt，还包含了system prompt、模型名、temperature和max_tokens，
        避免不同调用参数错误复用同一份结果。
        """
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
        """离线回退模式，大模型掉线仍然提供回复。"""
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
        """大模型调用主流程"""
        cache_ttl = cache_ttl or settings.LLM_CACHE_SECONDS  # 缓存数据存活时间
        cache_key = self._cache_key(system_prompt, prompt, temperature, max_tokens, self._config.model)  # 缓存key
        cached = cache.get(cache_key)  # 获取缓存
        if cached:
            return cached  # 匹配直接返回缓存

        client = self._get_client()  # 加载大模型
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