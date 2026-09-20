from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import __version__
from app.api import router as api_router
from app.config import get_settings
from app.db import dispose_engine, get_engine, get_sessionmaker
from app.instance import instance_id
from app.metrics import mark_instance_up
from app.middleware import InstanceHeaderMiddleware, SessionMiddleware
from app.models import Base
from app.redis_client import close_redis, get_redis
from app.seed import seed_if_empty
from app.web import router as web_router

logger = logging.getLogger("t2.startup")

# Общий для всех нод ключ advisory-блокировки PostgreSQL. Схему и демо-данные
# создаёт только тот экземпляр, который занял ключ первым, остальные ждут его.
SCHEMA_LOCK_KEY = 728_231_002


async def _wait_for(label: str, probe: Callable[[], Awaitable[None]]) -> None:
    """Ждать зависимость с повторами: в Swarm нет depends_on, порядок старта не гарантирован."""
    settings = get_settings()
    attempts = max(1, settings.startup_wait_attempts)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            await probe()
            return
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            logger.warning(
                "%s недоступен, попытка %d из %d: %s", label, attempt, attempts, exc
            )
            await asyncio.sleep(settings.startup_wait_delay_seconds)

    raise RuntimeError(f"{label} не ответил за {attempts} попыток") from last_error


async def _probe_database() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _probe_redis() -> None:
    await get_redis().ping()


async def wait_for_dependencies() -> None:
    await _wait_for("PostgreSQL", _probe_database)
    await _wait_for("Redis", _probe_redis)


async def prepare_schema() -> None:
    """Создать таблицы и демо-данные ровно один раз, даже если ноды стартуют одновременно."""
    engine = get_engine()
    async with engine.connect() as lock_conn:
        postgres = engine.dialect.name == "postgresql"
        if postgres:
            await lock_conn.execute(
                text("SELECT pg_advisory_lock(:key)"), {"key": SCHEMA_LOCK_KEY}
            )
            await lock_conn.commit()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with get_sessionmaker()() as session:
                await seed_if_empty(session)
        finally:
            if postgres:
                await lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": SCHEMA_LOCK_KEY}
                )
                await lock_conn.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await wait_for_dependencies()
    await prepare_schema()
    mark_instance_up()
    logger.info("Нода %s готова принимать запросы", instance_id())
    yield
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    application = FastAPI(
        title="t2 mobile",
        description=(
            "Учебный портал оператора t2. Приложение не терминирует TLS: "
            "сертификаты обрабатываются на Apache/Nginx."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    application.add_middleware(SessionMiddleware)
    application.add_middleware(InstanceHeaderMiddleware)
    static_dir = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static_dir), name="static")
    application.include_router(api_router, prefix="/api")
    application.include_router(web_router)
    application.state.settings = settings
    return application


app = create_app()
