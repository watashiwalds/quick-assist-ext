"""Fixture dùng chung.

Integration test cần PostgreSQL + pgvector:
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test
Không có biến này → test integration tự skip (unit/architecture vẫn chạy).
"""

import os
from collections.abc import AsyncIterator

import pytest

TEST_DB = os.getenv("TEST_DATABASE_URL")

os.environ.update({
    "APP_ENV": "test",
    "ENABLE_DEV_LOGIN": "true",
    "AI_PROVIDER": "mock",
    "JWT_SECRET": "test-secret-0123456789-0123456789-abcd",
    "LOG_LEVEL": "WARNING",
})
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if TEST_DB:
        return
    skip = pytest.mark.skip(reason="Cần TEST_DATABASE_URL (PostgreSQL + pgvector)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
async def _migrated() -> AsyncIterator[None]:
    from alembic import command
    from alembic.config import Config

    api_dir = os.path.dirname(os.path.dirname(__file__))
    cfg = Config(os.path.join(api_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(api_dir, "migrations"))
    cfg.attributes["database_url"] = TEST_DB
    import asyncio

    await asyncio.to_thread(command.downgrade, cfg, "base")
    await asyncio.to_thread(command.upgrade, cfg, "head")
    yield


@pytest.fixture
async def app(_migrated: None):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from quickassist.data.database import dispose_engine, get_engine
    from quickassist.main import create_app

    async with get_engine().begin() as conn:
        await conn.execute(text(
            "TRUNCATE users, jobs, idempotency_keys RESTART IDENTITY CASCADE"
        ))
    yield create_app()
    await dispose_engine()


@pytest.fixture
async def client(app):  # type: ignore[no-untyped-def]
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


async def login(client, email: str = "a@test.local") -> dict[str, str]:  # type: ignore[no-untyped-def]
    r = await client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
