from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as a_redis

from common.read_config import get_cache_options
from databases.sql.util import get_async_session
from databases.redis.util import get_async_redis
from databases.sql.category import repository as cate_repo
from databases.redis.cache import repository as redis_cache_repo
from databases.sql.cache import repository as sql_cache_repo
from domain.schemas.search import (
    SearchRequest,
    SearchResponse,
    InfoResponse,
    InfoRequest,
)
from app.search_api.search import SearchClient
from app.search_api.info import SearchInfo

router = APIRouter(prefix="/api", tags=["api"])

CALLER_TYPE = "api.search"


@router.post(
    "/search/",
    response_model=SearchResponse,
    description="渡された値から対象のURLの価格情報を返します。",
)
async def api_get_search_result(
    searchreq: SearchRequest,
    db: AsyncSession = Depends(get_async_session),
):
    if not searchreq.url and not searchreq.search_keyword:
        raise HTTPException(
            status_code=404, detail="URL or search keyword is required."
        )
    cache_options = get_cache_options()
    if cache_options.backend == "redis":
        searchcache_repo = redis_cache_repo.SearchCacheRedisRepository(
            r=get_async_redis(),
            expiry_seconds=cache_options.expires,
        )
    else:
        searchcache_repo = sql_cache_repo.SearchCacheRepository(ses=db)

    client = SearchClient(
        ses=db,
        searchrequest=searchreq,
        searchcache_repository=searchcache_repo,
        caller_type=CALLER_TYPE,
    )
    try:
        response = await client.execute()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return response


@router.post(
    "/search/info/",
    response_model=InfoResponse,
    description="渡された値からその他の情報を返します。",
)
async def api_get_search_info(
    inforeq: InfoRequest,
    db: AsyncSession = Depends(get_async_session),
):
    infoclient = SearchInfo(
        ses=db,
        caller_type=CALLER_TYPE,
        inforeq=inforeq,
        category_repo=cate_repo.CategoryRepository(ses=db),
    )
    try:
        response = await infoclient.execute()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return response
