from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import repo  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import init_db, make_engine, make_session_maker  # noqa: E402
from app.handlers import routers  # noqa: E402
from app.main import build_dispatcher  # noqa: E402
from tests.fake_telegram import FakeTelegram, Harness  # noqa: E402

ADMIN_ID = 100


@pytest_asyncio.fixture
async def env(tmp_path):
    """Fresh database + dispatcher + fake Telegram, each user in their Telegram language (BOT_LANGUAGE=auto)."""
    async for harness in _make_env(tmp_path, language="auto"):
        yield harness


@pytest_asyncio.fixture
async def env_en(tmp_path):
    """Same, with the default BOT_LANGUAGE=en: everyone gets English."""
    async for harness in _make_env(tmp_path, language="en"):
        yield harness


async def _make_env(tmp_path, language: str):
    """TEST_DATABASE_URL lets the same suite run against PostgreSQL."""
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = make_engine(url)
    if os.environ.get("TEST_DATABASE_URL"):
        from app.db import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await init_db(engine)
    session_maker = make_session_maker(engine)
    async with session_maker() as session:
        await repo.seed_defaults(session)
        await session.commit()
    settings = Settings(bot_token="42:TEST", admin_ids=frozenset({ADMIN_ID}), company_name="Northwind Studio",
                        broadcast_rate=0, language=language)
    api = FakeTelegram()
    harness = Harness(build_dispatcher(settings, session_maker), api)
    harness.session_maker = session_maker
    harness.settings = settings
    yield harness
    await engine.dispose()
    # Module-level routers can be attached to one dispatcher at a time; detach them for the next test.
    for router in routers():
        router._parent_router = None


@pytest.fixture
def admin(env):
    return env.user(ADMIN_ID, "Max", "max_northwind")


def link_code(text: str, prefix: str = "b_") -> str:
    match = re.search(rf"start={prefix}([A-Za-z0-9_-]+)", text)
    assert match, f"no {prefix} link in: {text!r}"
    return match.group(1)
