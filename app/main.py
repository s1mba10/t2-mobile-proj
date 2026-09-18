from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import __version__
from app.api import router as api_router
from app.config import get_settings
from app.db import dispose_engine, get_engine, get_sessionmaker
from app.middleware import InstanceHeaderMiddleware, SessionMiddleware
from app.models import Base
from app.redis_client import close_redis, get_redis
from app.seed import seed_if_empty
from app.web import router as web_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("SELECT 1"))
    async with get_sessionmaker()() as session:
        await seed_if_empty(session)
    await get_redis().ping()
    yield
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
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
