#!/usr/bin/env python
from __future__ import annotations

import os
import socket
import sys
import time
from urllib.parse import urlparse

import psycopg
import redis


def wait_for_postgres(database_url: str, retries: int = 30, delay: int = 2) -> None:
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    sync_url = database_url.replace("+asyncpg", "")
    for i in range(1, retries + 1):
        try:
            with psycopg.connect(sync_url, connect_timeout=3):
                pass
            print("[wait_for_services] postgres ready")
            return
        except Exception as exc:
            print(f"[wait_for_services] postgres not ready ({i}/{retries}): {exc}")
            time.sleep(delay)

    raise RuntimeError("postgres did not become ready in time")


def wait_for_redis(redis_url: str, retries: int = 30, delay: int = 2) -> None:
    if not redis_url:
        raise RuntimeError("REDIS_URL is required")

    for i in range(1, retries + 1):
        try:
            client = redis.Redis.from_url(redis_url)
            client.ping()
            print("[wait_for_services] redis ready")
            return
        except Exception as exc:
            print(f"[wait_for_services] redis not ready ({i}/{retries}): {exc}")
            time.sleep(delay)

    raise RuntimeError("redis did not become ready in time")


def wait_for_rabbitmq(rabbitmq_url: str, retries: int = 30, delay: int = 2) -> None:
    if not rabbitmq_url:
        raise RuntimeError("RABBITMQ_URL is required")

    parsed = urlparse(rabbitmq_url)
    host = parsed.hostname or "rabbitmq"
    port = parsed.port or 5672

    for i in range(1, retries + 1):
        try:
            with socket.create_connection((host, port), timeout=3):
                print("[wait_for_services] rabbitmq ready")
                return
        except Exception as exc:
            print(f"[wait_for_services] rabbitmq not ready ({i}/{retries}): {exc}")
            time.sleep(delay)

    raise RuntimeError("rabbitmq did not become ready in time")


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")
    rabbitmq_url = os.getenv("RABBITMQ_URL", "")

    try:
        wait_for_postgres(database_url)
        wait_for_redis(redis_url)
        wait_for_rabbitmq(rabbitmq_url)
    except Exception as exc:
        print(f"[wait_for_services] failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
