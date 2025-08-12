import pytest
import redis.asyncio as a_redis

from common import read_config
from domain.schemas.search import SearchRequest
from app.search_api import search, repository


class TestSearchClient:

    @pytest.mark.asyncio
    async def test_wait_downloadable_no_cache(self):
        sclient = search.SearchClient(
            ses=None,
            searchrequest=SearchRequest(
                url="", search_keyword="", sitename="", options={}
            ),
            searchcache_repository=None,
            caller_type="test",
        )
        redisopts = read_config.get_redis_options()
        cacheopts = read_config.get_cache_options()
        domainrepo = repository.URLDomainCacheRepository(
            r=a_redis.Redis(host=redisopts.host, port=redisopts.port, db=redisopts.db),
            expiry_seconds=cacheopts.expires,
        )
        wait_time_util_dl = 30
        ok, msg = await sclient._wait_downloadable(
            domain="test_domain",
            repository=domainrepo,
            wait_time_util_downloadable=wait_time_util_dl,
        )
        assert ok == True
        assert msg == ""
