from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings
from app.instance import hostname, instance_id
from app.redis_client import get_redis
from app.services import get_subscriber_by_id
from app.sessions import RedisSessionStore, record_hit, session_id_from


class InstanceHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Backend-Instance"] = instance_id()
        response.headers["X-Backend-Hostname"] = hostname()
        response.headers["X-Backend-TLS"] = "terminated-upstream"
        return response


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        redis = get_redis()
        store = RedisSessionStore(redis, settings)
        sid = session_id_from(request, settings)
        session = await store.load(sid)
        request.state.session_id = sid
        request.state.session = session
        request.state.subscriber = None

        if session and session.get("subscriber_id"):
            from app.db import get_sessionmaker

            async with get_sessionmaker()() as db:
                request.state.subscriber = await get_subscriber_by_id(
                    db, int(session["subscriber_id"])
                )

        if not request.url.path.startswith("/static"):
            await record_hit(redis, request.url.path)

        return await call_next(request)
