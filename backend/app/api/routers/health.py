from __future__ import annotations

import asyncio
import socket
from urllib.parse import urlparse

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import settings

router = APIRouter(tags=["health"])


async def _check_rabbitmq() -> bool:
    parsed = urlparse(settings.rabbitmq_url)
    host = parsed.hostname or "rabbitmq"
    port = parsed.port or 5672

    def _connect() -> bool:
        with socket.create_connection((host, port), 2):
            return True

    try:
        await asyncio.to_thread(_connect)
        return True
    except Exception:
        return False


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db_session)) -> dict:
    db_ok = False
    redis_ok = False

    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        redis_ok = await client.ping()
    except Exception:
        redis_ok = False
    finally:
        await client.aclose()

    rabbit_ok = await _check_rabbitmq()
    overall = "ok" if db_ok and redis_ok and rabbit_ok else "degraded"

    return {
        "status": overall,
        "services": {
            "database": db_ok,
            "redis": redis_ok,
            "rabbitmq": rabbit_ok,
        },
    }
