from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILES = (
    str(Path(__file__).resolve().parents[3] / ".env"),
    ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "Project Phoenix"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    app_secret_key: str = "change-me-in-production-with-at-least-32-bytes"
    access_token_expire_minutes: int = 60 * 8
    jwt_algorithm: str = "HS256"

    api_v1_prefix: str = "/api/v1"
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://127.0.0.1", "http://localhost:5173"]
    )

    database_url: str = "postgresql+asyncpg://phoenix:phoenix123@db:5432/phoenix"
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://phoenix:phoenix123@rabbitmq:5672//"

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    rag_top_k: int = 5
    rag_cache_seconds: int = 3600
    session_cache_seconds: int = 600
    llm_cache_seconds: int = 600
    embedding_model: str = ""

    celery_worker_concurrency: int = 2
    celery_task_soft_time_limit: int = 180
    celery_task_time_limit: int = 240

    uvicorn_workers: int = 2
    trusted_proxy_headers: bool = True
    enable_hsts: bool = False

    @field_validator("allowed_hosts", "cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return ["*"]
        return [item.strip() for item in value.split(",") if item.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on", "debug", "development"}:
                return True
            if lowered in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def data_dir(self) -> Path:
        path = self.base_dir / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def vector_store_dir(self) -> Path:
        path = self.data_dir / "vector_store"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def vector_index_path(self) -> Path:
        return self.vector_store_dir / "index.faiss"

    @property
    def vector_meta_path(self) -> Path:
        return self.vector_store_dir / "index_meta.json"

    @property
    def interview_questions_path(self) -> Path:
        return self.data_dir / "interview_questions.md"

    @property
    def sqlalchemy_async_database_uri(self) -> str:
        if "+asyncpg" in self.database_url:
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    @property
    def sqlalchemy_sync_database_uri(self) -> str:
        if "+asyncpg" in self.database_url:
            return self.database_url.replace("+asyncpg", "+psycopg", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
