from contextlib import asynccontextmanager

from fastapi import FastAPI

from routers import (
    api,
)
from databases.redis.util import get_async_redis
from app.search_api.repository import URLDomainCacheRepository
from databases.sql.create_table import create_table


@asynccontextmanager
async def lifespan(app: FastAPI):
    await delete_all_domain_cache()
    create_table()
    yield


async def delete_all_domain_cache():
    repo = URLDomainCacheRepository(r=get_async_redis())
    await repo.delete_all()


app = FastAPI(lifespan=lifespan)

app.include_router(api.router)
