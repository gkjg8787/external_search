from sqlmodel import SQLModel, create_engine
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)

from common import read_config

databases = read_config.get_databases()
sync_db_params = URL.create(**databases.sync.model_dump(exclude_none=True))
async_db_params = URL.create(**databases.a_sync.model_dump(exclude_none=True))

sub_params = {
    "echo": False,
}
if "sqlite" in databases.sync.drivername or "sqlite" in databases.a_sync.drivername:
    sub_params["connect_args"] = {"check_same_thread": False}

engine = create_engine(sync_db_params, **sub_params)

async_engine = create_async_engine(async_db_params, **sub_params)
aSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=async_engine)


async def get_async_session():
    async with aSessionLocal() as ses:
        yield ses


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


async def create_async_db_and_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def get_engine():
    return engine


def get_async_engine():
    return async_engine
