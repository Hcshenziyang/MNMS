#!/usr/bin/env python
from __future__ import annotations

import os
import sys
import time
from urllib.parse import urlparse

import pymysql
import redis


def wait_for_mysql(database_url: str, retries: int = 30, delay: int = 2) -> None:
    parsed = urlparse(database_url)
    if not parsed.scheme.startswith("mysql"):
        print("[wait_for_db] DATABASE_URL is not mysql, skip mysql wait")
        return

    host = parsed.hostname or "db"
    port = parsed.port or 3306
    user = parsed.username or "root"
    password = parsed.password or ""
    database = parsed.path.lstrip("/")

    for i in range(1, retries + 1):
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                connect_timeout=3,
                read_timeout=3,
                write_timeout=3,
            )
            conn.close()
            print("[wait_for_db] mysql ready")
            return
        except Exception as exc:
            print(f"[wait_for_db] mysql not ready ({i}/{retries}): {exc}")
            time.sleep(delay)

    raise RuntimeError("mysql did not become ready in time")


def wait_for_redis(redis_url: str, retries: int = 30, delay: int = 2) -> None:
    if not redis_url:
        print("[wait_for_db] REDIS_URL not set, skip redis wait")
        return

    for i in range(1, retries + 1):
        try:
            client = redis.Redis.from_url(redis_url)
            client.ping()
            print("[wait_for_db] redis ready")
            return
        except Exception as exc:
            print(f"[wait_for_db] redis not ready ({i}/{retries}): {exc}")
            time.sleep(delay)

    raise RuntimeError("redis did not become ready in time")


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")

    try:
        wait_for_mysql(database_url)
        wait_for_redis(redis_url)
    except Exception as exc:
        print(f"[wait_for_db] failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())