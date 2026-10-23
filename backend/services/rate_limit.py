from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import Request

from backend.errors import AppError
from backend.services.security import client_ip
from core.config import get_settings

logger = logging.getLogger(__name__)

_redis = None
_redis_ready: bool | None = None
_memory: dict[str, Deque[float]] = defaultdict(deque)


def parse_rule(rule: str, default: tuple[int, int] = (60, 60)) -> tuple[int, int]:
    """«۳۰/۶۰» یعنی ۳۰ درخواست در ۶۰ ثانیه."""
    try:
        count, window = rule.split("/")
        return max(1, int(count)), max(1, int(window))
    except Exception:
        return default


async def _get_redis():
    global _redis, _redis_ready
    if _redis_ready is False:
        return None
    if _redis is not None:
        return _redis
    settings = get_settings()
    if not settings.redis_url:
        _redis_ready = False
        return None
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.4,
            socket_timeout=0.4,
        )
        await client.ping()
        _redis = client
        _redis_ready = True
        return client
    except Exception as exc:
        logger.warning("Redis برای rate limit در دسترس نیست (%s)؛ از حافظه استفاده می‌شود", exc)
        _redis_ready = False
        return None


async def _hit_redis(client, key: str, limit: int, window: int) -> tuple[bool, int]:
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = await pipe.execute()
    if ttl is None or ttl < 0:
        await client.expire(key, window)
        ttl = window
    return int(count) <= limit, int(ttl)


def _hit_memory(key: str, limit: int, window: int) -> tuple[bool, int]:
    now = time.time()
    bucket = _memory[key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = int(window - (now - bucket[0])) + 1
        return False, max(1, retry_after)
    bucket.append(now)
    return True, window


async def enforce(request: Request, scope: str, rule: str, identity: str | None = None) -> None:
    """اگر سقف رد شد، AppError('RATE_LIMITED') می‌اندازد."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    limit, window = parse_rule(rule)
    who = identity or client_ip(request) or "anon"
    key = f"rl:{scope}:{who}"

    client = await _get_redis()
    if client is not None:
        try:
            allowed, retry_after = await _hit_redis(client, key, limit, window)
        except Exception as exc:
            logger.warning("خطای Redis در rate limit: %s", exc)
            allowed, retry_after = _hit_memory(key, limit, window)
    else:
        allowed, retry_after = _hit_memory(key, limit, window)

    if not allowed:
        raise AppError("RATE_LIMITED", extra={"retry_after": retry_after})


async def limit_login(request: Request, identity: str | None = None) -> None:
    await enforce(request, "login", get_settings().rate_limit_login, identity)


async def limit_register(request: Request) -> None:
    await enforce(request, "register", get_settings().rate_limit_register)


async def limit_chat(request: Request, identity: str | None = None) -> None:
    await enforce(request, "chat", get_settings().rate_limit_chat, identity)


async def limit_default(request: Request, scope: str = "api") -> None:
    await enforce(request, scope, get_settings().rate_limit_default)
