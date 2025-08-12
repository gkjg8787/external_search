from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as a_redis

from common.read_config import get_cache_options, get_redis_options
from databases.sql.util import get_async_session
from databases.redis.cache import repository as redis_cache_repo
from databases.sql.cache import repository as sql_cache_repo
from domain.schemas.search import SearchRequest, SearchResponse
from app.search_api.search import SearchClient

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
        redisopts = get_redis_options()
        searchcache_repo = redis_cache_repo.SearchCacheRedisRepository(
            r=a_redis.Redis(host=redisopts.host, port=redisopts.port, db=redisopts.db),
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
