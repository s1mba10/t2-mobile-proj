import os
from collections.abc import Iterator
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test-t2.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("INSTANCE_ID", "test-node")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.config import get_settings  # noqa: E402
from app.db import dispose_engine  # noqa: E402
from app.redis_client import set_redis  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    db_path = Path("test-t2.db")
    if db_path.exists():
        db_path.unlink()

    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    set_redis(fake)

    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    import asyncio

    asyncio.run(dispose_engine())
    set_redis(None)
    if db_path.exists():
        db_path.unlink()
