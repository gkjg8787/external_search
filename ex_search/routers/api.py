import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog


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
    request: Request,
    searchreq: SearchRequest,
    db: AsyncSession = Depends(get_async_session),
):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        router_path=request.url.path,
        request_id=str(uuid.uuid4()),
    )
    log = structlog.get_logger(__name__)
    log.info("API Search called", searchreq=searchreq)
    if not searchreq.url and not searchreq.search_keyword:
        log.warning("URL or search keyword is required.")
        raise HTTPException(
            status_code=404, detail="URL or search keyword is required."
        )
    cache_options = get_cache_options()
    log.debug("Cache options", options=cache_options)
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
        log.error("Search execution failed", error_type=type(e).__name__, error=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    return response


@router.post(
    "/search/info/",
    response_model=InfoResponse,
    description="渡された値からその他の情報を返します。",
)
async def api_get_search_info(
    request: Request,
    inforeq: InfoRequest,
    db: AsyncSession = Depends(get_async_session),
):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        router_path=request.url.path,
        request_id=str(uuid.uuid4()),
    )
    log = structlog.get_logger(__name__)
    log.info("API Info called", inforeq=inforeq)
    infoclient = SearchInfo(
        ses=db,
        caller_type=CALLER_TYPE,
        inforeq=inforeq,
        category_repo=cate_repo.CategoryRepository(ses=db),
    )
    try:
        response = await infoclient.execute()
    except Exception as e:
        log.error("Info execution failed", error_type=type(e).__name__, error=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    return response
