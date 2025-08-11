import pytest

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)
from sqlmodel import SQLModel, create_engine

from main import app
from tests.db_settings import DATABASES
from domain.models.activitylog import activitylog
from domain.models.cache import cache
from domain.models.category import category
from databases.sql.util import get_async_session


@pytest.fixture(scope="session")
async def test_db():
    ASYNC_TEST_DB_URL = URL.create(**DATABASES["a_sync"])
    SYNC_TEST_DB_URL = URL.create(**DATABASES["sync"])
    is_echo = False
    async_engine = create_async_engine(ASYNC_TEST_DB_URL, echo=is_echo)
    engine = create_engine(SYNC_TEST_DB_URL, echo=is_echo)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    TestingSessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=async_engine
    )

    async def get_db_for_testing():
        async with TestingSessionLocal() as ses:
            yield ses

    # 　テスト時に依存するDBを本番用からテスト用のものに切り替える
    app.dependency_overrides[get_async_session] = get_db_for_testing
    async with TestingSessionLocal() as ses:
        yield ses

    await async_engine.dispose()
