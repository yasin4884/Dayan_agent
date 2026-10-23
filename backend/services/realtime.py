from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

from core.config import get_settings

logger = logging.getLogger(__name__)

# اگر Redis باشد، پیام بین همه ورکرها پخش می‌شود (لازم برای ۱M کاربر و چند ورکر).
# اگر نباشد، فقط داخل همین پروسه کار می‌کند.
_CHANNEL_PREFIX = "rt:"
_PRESENCE_TTL = 120  # پشتیبان Redis بین ورکرها؛ حضور واقعی از سوکت زنده می‌آید


class Connection:
    """یک وب‌سوکت به‌همراه هویت صاحبش."""

    __slots__ = ("ws", "room", "actor_id", "actor_type", "actor_name")

    def __init__(self, ws: WebSocket, room: str, actor_id: str, actor_type: str, actor_name: str):
        self.ws = ws
        self.room = room
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.actor_name = actor_name

    async def send(self, event: dict[str, Any]) -> bool:
        if self.ws.client_state != WebSocketState.CONNECTED:
            return False
        try:
            await self.ws.send_text(json.dumps(event, ensure_ascii=False))
            return True
        except Exception:
            return False


class RealtimeHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[Connection]] = defaultdict(set)
        self._redis = None
        self._redis_checked = False
        self._pubsub_task: asyncio.Task | None = None
        # حضور محلی: room -> {actor_key: (last_seen, actor_type, name)}
        self._presence: dict[str, dict[str, tuple[float, str, str]]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    # ---------------- Redis ----------------

    async def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        settings = get_settings()
        if not settings.redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await client.ping()
            self._redis = client
            self._pubsub_task = asyncio.create_task(self._listen())
            logger.info("Realtime روی Redis Pub/Sub فعال شد")
        except Exception as exc:
            logger.warning("Redis برای realtime در دسترس نیست (%s)؛ فقط همین پروسه", exc)
            self._redis = None
        return self._redis

    async def _listen(self) -> None:
        """پیام‌های ورکرهای دیگر را می‌گیرد و به سوکت‌های محلی می‌دهد."""
        try:
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe(f"{_CHANNEL_PREFIX}*")
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                channel = str(message.get("channel") or "")
                room = channel[len(_CHANNEL_PREFIX) :]
                try:
                    payload = json.loads(message.get("data") or "{}")
                except Exception:
                    continue
                await self._fanout_local(room, payload, skip_origin=payload.pop("_origin", None))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("حلقه Pub/Sub قطع شد: %s", exc)

    # ---------------- اتصال ----------------

    async def connect(
        self, ws: WebSocket, room: str, actor_id: str, actor_type: str, actor_name: str
    ) -> Connection:
        await ws.accept()
        await self._get_redis()
        conn = Connection(ws, room, actor_id, actor_type, actor_name)
        async with self._lock:
            self._rooms[room].add(conn)
            self._presence[room][f"{actor_type}:{actor_id}"] = (time.time(), actor_type, actor_name)
        await self.broadcast(
            room,
            {
                "type": "presence",
                "actor_type": actor_type,
                "actor_name": actor_name,
                "online": True,
                "members": await self.members(room),
            },
        )
        return conn

    async def disconnect(self, conn: Connection) -> None:
        async with self._lock:
            self._rooms[conn.room].discard(conn)
            if not self._rooms[conn.room]:
                self._rooms.pop(conn.room, None)
            key = f"{conn.actor_type}:{conn.actor_id}"
            still_here = any(
                c.actor_id == conn.actor_id and c.actor_type == conn.actor_type
                for c in self._rooms.get(conn.room, set())
            )
            if not still_here:
                self._presence.get(conn.room, {}).pop(key, None)
        await self.broadcast(
            conn.room,
            {
                "type": "presence",
                "actor_type": conn.actor_type,
                "actor_name": conn.actor_name,
                "online": False,
                "members": await self.members(conn.room),
            },
        )

    async def members(self, room: str) -> list[dict[str, str]]:
        """اعضای آنلاین اتاق — اولویت با سوکت‌های زنده، بعد Redis بین ورکرها."""
        now = time.time()
        local: dict[str, tuple[float, str, str]] = {}
        async with self._lock:
            for conn in list(self._rooms.get(room, set())):
                if conn.ws.client_state != WebSocketState.CONNECTED:
                    continue
                key = f"{conn.actor_type}:{conn.actor_id}"
                entry = (now, conn.actor_type, conn.actor_name)
                local[key] = entry
                self._presence[room][key] = entry
        client = await self._get_redis()
        if client is not None:
            try:
                for key, value in local.items():
                    await client.hset(
                        f"presence:{room}",
                        key,
                        json.dumps([value[0], value[1], value[2]]),
                    )
                raw = await client.hgetall(f"presence:{room}")
                for key, value in (raw or {}).items():
                    if key in local:
                        continue
                    try:
                        seen, actor_type, name = json.loads(value)
                    except Exception:
                        continue
                    if now - float(seen) < _PRESENCE_TTL:
                        local[key] = (float(seen), actor_type, name)
                await client.expire(f"presence:{room}", _PRESENCE_TTL * 2)
            except Exception:
                pass
        return [
            {"actor_type": value[1], "actor_name": value[2]}
            for value in sorted(local.values(), key=lambda v: v[1])
        ]

    async def touch(self, conn: Connection) -> None:
        """تازه‌کردن مهلت حضور روی هر پیام دریافتی."""
        async with self._lock:
            self._presence[conn.room][f"{conn.actor_type}:{conn.actor_id}"] = (
                time.time(),
                conn.actor_type,
                conn.actor_name,
            )

    # ---------------- پخش ----------------

    async def _fanout_local(
        self, room: str, event: dict[str, Any], skip_origin: str | None = None
    ) -> None:
        dead: list[Connection] = []
        for conn in list(self._rooms.get(room, set())):
            if skip_origin and f"{conn.actor_type}:{conn.actor_id}" == skip_origin:
                continue
            if not await conn.send(event):
                dead.append(conn)
        for conn in dead:
            self._rooms.get(room, set()).discard(conn)

    async def broadcast(
        self, room: str, event: dict[str, Any], skip_origin: str | None = None
    ) -> None:
        await self._fanout_local(room, event, skip_origin=skip_origin)
        client = await self._get_redis()
        if client is None:
            return
        try:
            payload = dict(event)
            if skip_origin:
                payload["_origin"] = skip_origin
            await client.publish(f"{_CHANNEL_PREFIX}{room}", json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            logger.debug("انتشار Redis ناموفق: %s", exc)

    async def close(self) -> None:
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:
                pass


_hub: RealtimeHub | None = None


def get_hub() -> RealtimeHub:
    global _hub
    if _hub is None:
        _hub = RealtimeHub()
    return _hub


def ticket_room(ticket_id: str) -> str:
    return f"ticket:{ticket_id}"


ADMIN_INBOX = "admin:inbox"
