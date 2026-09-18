from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Request, Response
from redis.asyncio import Redis

from app.config import Settings
from app.instance import instance_id


class RedisSessionStore:
    """Сессии живут в Redis, общем для всех нод приложения."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def load(self, session_id: str | None) -> dict[str, Any] | None:
        if not session_id:
            return None
        raw = await self.redis.get(self._key(session_id))
        if not raw:
            return None
        await self.redis.expire(self._key(session_id), self.settings.session_ttl_seconds)
        return json.loads(raw)

    async def create(self, payload: dict[str, Any]) -> str:
        session_id = str(uuid.uuid4())
        await self.redis.set(
            self._key(session_id),
            json.dumps(payload),
            ex=self.settings.session_ttl_seconds,
        )
        return session_id

    async def destroy(self, session_id: str | None) -> None:
        if session_id:
            await self.redis.delete(self._key(session_id))

    def attach_cookie(self, response: Response, session_id: str) -> None:
        response.set_cookie(
            self.settings.session_cookie_name,
            session_id,
            max_age=self.settings.session_ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=self.settings.session_cookie_secure,
            path="/",
        )

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(self.settings.session_cookie_name, path="/")


async def record_hit(redis: Redis, path: str) -> None:
    entry = json.dumps({"instance_id": instance_id(), "path": path})
    await redis.lpush("t2:hits", entry)
    await redis.ltrim("t2:hits", 0, 19)


async def recent_hits(redis: Redis) -> list[dict[str, str]]:
    raw = await redis.lrange("t2:hits", 0, 19)
    return [json.loads(item) for item in raw]


def session_id_from(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.session_cookie_name)
