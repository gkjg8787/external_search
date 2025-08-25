from typing import Callable
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
import uuid
import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession


from common import read_config
from domain.schemas.search import SearchRequest, SearchResponse
from domain.models.cache import (
    cache as c_cache,
    command as c_cmd,
    enums as c_enums,
    repository as i_cacherepo,
)
from domain.models.activitylog import enums as act_enums
from databases.redis.util import get_async_redis
from app.sofmap import (
    web_scraper as sofmap_scraper,
    model_convert as sofmap_modelconvert,
    urlgenerate as sofmap_urlgenerate,
    category as sofmap_category,
    tasks as sofmap_tasks,
)
from app.geo import (
    urlgenerate as geo_urlgenerate,
    web_scraper as geo_scraper,
    model_convert as geo_modelconvert,
    tasks as geo_tasks,
)
from app.activitylog.update import UpdateActivityLog
from .enums import SuppoertedDomain, SupportedSiteName, ActivityName, URLDomainStatus
from .repository import URLDomainCacheRepository

CYCLE_WAIT_TIME = 1.5


class SearchClient:
    session: AsyncSession
    searchrequest: SearchRequest
    caller_type: str
    searchcache_repository: i_cacherepo.ISearchCacheRepository

    def __init__(
        self,
        ses: AsyncSession,
        searchrequest: SearchRequest,
        searchcache_repository: i_cacherepo.ISearchCacheRepository,
        caller_type: str = "",
    ):
        self.session = ses
        self.searchrequest = searchrequest
        self.caller_type = caller_type
        self.searchcache_repository = searchcache_repository

    async def execute(self) -> SearchResponse:
        searchrequest: SearchRequest = self.searchrequest
        upactlog = UpdateActivityLog(ses=self.session)
        init_subinfo = {"request": searchrequest.model_dump()}
        if searchrequest.search_keyword and not searchrequest.url:
            urlgenerator = KeyWordToURL(ses=self.session, searchrequest=searchrequest)
            try:
                searchrequest.url = await urlgenerator.execute()
            except Exception as e:
                await upactlog.create(
                    target_id=str(uuid.uuid4()),
                    target_table="None",
                    activity_type=ActivityName.SearchClient.value,
                    status=act_enums.UpdateStatus.FAILED.name,
                    caller_type=self.caller_type,
                    error_msg=str(e),
                    subinfo=init_subinfo,
                )
                return SearchResponse(error_msg=str(e))
        parsed_url = urlparse(searchrequest.url)
        match parsed_url.netloc:
            case SuppoertedDomain.SOFMAP.value | SuppoertedDomain.A_SOFMAP.value:
                if searchrequest.options.get("convert_to_direct_search"):
                    converted_url = sofmap_urlgenerate.convert_to_direct_search(
                        url=searchrequest.url
                    )
                    if searchrequest.url != converted_url:
                        init_subinfo["convert_to"] = converted_url
                else:
                    converted_url = searchrequest.url
            case _:
                converted_url = searchrequest.url

        tasklog = await upactlog.create(
            target_id=str(uuid.uuid4()),
            target_table=parsed_url.netloc,
            activity_type=ActivityName.SearchClient.value,
            caller_type=self.caller_type,
            subinfo=init_subinfo,
        )

        if not tasklog:
            return SearchResponse(error_msg=f"task is not created")

        tasklog_id = tasklog.id
        ok, result = await self._download_html(converted_url=converted_url)
        if not ok:
            await upactlog.failed(
                id=tasklog_id,
                error_msg=result,
            )
            return SearchResponse(error_msg=result)
        add_subinfo = {}
        if searchrequest.options.get(
            "remove_duplicates"
        ) is None or searchrequest.options.get("remove_duplicates"):
            remove_duplicates = True
            add_subinfo["remove_duplicates"] = True
        else:
            remove_duplicates = False
            add_subinfo["remove_duplicates"] = False

        match parsed_url.netloc:
            case SuppoertedDomain.SOFMAP.value | SuppoertedDomain.A_SOFMAP.value:
                parsed_result = await sofmap_scraper.parse_html(
                    html=result.download_text, url=searchrequest.url
                )
                sresults = (
                    sofmap_modelconvert.ModelConverter.parseresults_to_searchresults(
                        results=parsed_result, remove_duplicates=remove_duplicates
                    )
                )
                response = SearchResponse(**sresults.model_dump())
            case SuppoertedDomain.GEO.value:
                parsed_result = await geo_scraper.parse_html(
                    html=result.download_text, url=searchrequest.url
                )
                sresults = (
                    geo_modelconvert.ModelConverter.parseresults_to_searchresults(
                        results=parsed_result
                    )
                )
                response = SearchResponse(**sresults.model_dump())
            case _:
                await upactlog.failed(
                    id=tasklog_id,
                    error_msg=f"parse error. not supported domain :{parsed_url.netloc}",
                )
                return SearchResponse(
                    error_msg=f"not supported domain : {parsed_url.netloc}"
                )
        if not result.id:
            cacheopts = read_config.get_cache_options()
            if cacheopts.expires:
                cache_expires = datetime.now(timezone.utc) + timedelta(
                    seconds=cacheopts.expires
                )
                result.expires = cache_expires
                await self._set_search_cache(
                    searchcache=result,
                )
        await upactlog.completed(id=tasklog_id)
        return response

    async def _get_search_cache(self) -> c_cache.SearchCache | None:
        repo = self.searchcache_repository
        now = datetime.now(timezone.utc)
        results = await repo.get(
            command=c_cmd.SearchCacheGetCommand(
                url=self.searchrequest.url, expires_start=now
            )
        )
        if not results:
            return None
        return max(results, key=lambda x: x.created_at)

    async def _set_search_cache(
        self,
        searchcache: c_cache.SearchCache,
    ):
        repo = self.searchcache_repository
        await repo.save(data=searchcache)

    async def _create_URLDomainCacheRepository(self):
        cacheopts = read_config.get_cache_options()
        domainrepo = URLDomainCacheRepository(
            r=get_async_redis(),
            expiry_seconds=cacheopts.expires,
        )
        return domainrepo

    async def _wait_downloadable(
        self,
        domain: str,
        repository: URLDomainCacheRepository,
        timeout_util_downloadable: int,
    ):
        cached_data = await repository.get(domain)
        if not cached_data:
            return True, ""
        if cached_data.get("updated_at") and not isinstance(
            cached_data["updated_at"], datetime
        ):
            raise ValueError(f"cached_date has not datetime, {cached_data}")

        wait_start_time = time.perf_counter()

        def is_timeout(wait_start_time):
            return time.perf_counter() - wait_start_time > timeout_util_downloadable

        while True:
            cached_data = await repository.get(domain)
            if not cached_data:
                return True, ""
            if (
                cached_data.get("status")
                and cached_data["status"] == URLDomainStatus.DOWNLOADING.value
            ):
                await asyncio.sleep(CYCLE_WAIT_TIME)
                if is_timeout(wait_start_time):
                    return (
                        False,
                        f"time out, The time to wait for the update to finish has expired."
                        f"cache updated_at:{cached_data.get('updated_at')}"
                        f" wait_time_util_dl:{timeout_util_downloadable}"
                        f" status:{cached_data.get('status')}",
                    )
                continue
            cached_update = cached_data.get("updated_at")
            now = datetime.now(timezone.utc) - cached_update
            if int(now.total_seconds()) > CYCLE_WAIT_TIME:
                return True, ""
            await asyncio.sleep(CYCLE_WAIT_TIME)
            if is_timeout(wait_start_time):
                return (
                    False,
                    f"time out, The time to wait for the update to finish has expired."
                    f"cache updated_at:{cached_data.get('updated_at')}"
                    f" wait_time_util_dl:{timeout_util_downloadable}"
                    f" diff_time:{now.total_seconds()}",
                )

    async def _download_html(self, converted_url: str | None = None):
        searchrequest = self.searchrequest
        if converted_url and converted_url != searchrequest.url:
            target_url = converted_url
        else:
            target_url = searchrequest.url
        parsed_url = urlparse(target_url)
        searchcache = await self._get_search_cache()
        if searchcache and searchcache.download_text:
            return True, searchcache
        else:
            dl_waittimeopts = read_config.get_download_waittime_options()
            domainrepo = await self._create_URLDomainCacheRepository()
            ok, msg = await self._wait_downloadable(
                domain=parsed_url.netloc,
                repository=domainrepo,
                timeout_util_downloadable=dl_waittimeopts.timeout_util_downloadable,
            )
            if not ok:
                return False, msg
            searchopts = read_config.get_search_options()
            await domainrepo.save(
                domain=parsed_url.netloc, status=URLDomainStatus.DOWNLOADING.value
            )
            match parsed_url.netloc:
                case SuppoertedDomain.SOFMAP.value | SuppoertedDomain.A_SOFMAP.value:
                    if sofmap_urlgenerate.is_direct_search(url=target_url):
                        ok, result = await sofmap_scraper.get_html(
                            sofmap_scraper.GetCommandWithHttpx(
                                url=target_url,
                                timeout=dl_waittimeopts.timeout_for_each_url,
                                delay_seconds=dl_waittimeopts.min_wait_time_of_dl,
                                is_ucaa=not searchopts.safe_search,
                            )
                        )
                        download_type = c_enums.DownloadType.HTTPX.value
                    else:
                        ok, result = await sofmap_tasks.async_download_sofmap(
                            url=target_url
                        )
                        download_type = c_enums.DownloadType.SELENIUM.value
                case SuppoertedDomain.GEO.value:
                    ok, result = await geo_tasks.async_download_geo(url=target_url)
                    download_type = c_enums.DownloadType.SELENIUM.value
                case _:
                    await domainrepo.save(
                        domain=parsed_url.netloc, status=URLDomainStatus.FAILED.value
                    )
                    return False, f"not supported domain : {parsed_url.netloc}"
            if not ok:
                await domainrepo.save(
                    domain=parsed_url.netloc, status=URLDomainStatus.FAILED.value
                )
                return False, result
            await domainrepo.save(
                domain=parsed_url.netloc, status=URLDomainStatus.COMPLETED.value
            )
            searchcache = c_cache.SearchCache(
                domain=parsed_url.netloc,
                url=target_url,
                download_type=download_type,
                download_text=result,
            )
            return ok, searchcache


class KeyWordToURL:
    session: AsyncSession
    searchrequest: SearchRequest

    def __init__(self, ses: AsyncSession, searchrequest: SearchRequest):
        self.session = ses
        self.searchrequest = searchrequest

    async def execute(self) -> str:
        searchrequest: SearchRequest = self.searchrequest
        match searchrequest.sitename.lower():
            case SupportedSiteName.SOFMAP.value:
                return await self._build_sofmap_url(searchrequest)
            case SupportedSiteName.GEO.value:
                return await self._build_geo_url(searchrequest)
            case _:
                raise ValueError(
                    f"not supported sitename : {searchrequest.sitename.lower()}"
                )

    async def _build_geo_url(self, searchrequest: SearchRequest):
        params = {
            "search_keyword": searchrequest.search_keyword,
        }
        return geo_urlgenerate.build_search_url(**params)

    async def _build_sofmap_url(self, searchrequest: SearchRequest):
        params = {
            "search_keyword": searchrequest.search_keyword,
        }
        if searchrequest.options:
            extraction_any_keys = [
                "is_akiba",
                "direct_search",
                "product_type",
                "gid",
                "order_by",
            ]
            extraction_int_keys = ["display_count"]
            any_params = self._extract_params(
                options=searchrequest.options, target_keys=extraction_any_keys
            )
            int_params = self._extract_params(
                options=searchrequest.options,
                target_keys=extraction_int_keys,
                convert_value=lambda x: int(x),
            )
            category_name = searchrequest.options.get("category")
            if not any_params.get("gid") and category_name:
                gid = await sofmap_category.get_category_id(
                    ses=self.session,
                    is_akiba=any_params.get("is_akiba", False),
                    category_name=category_name,
                )
                if gid:
                    any_params["gid"] = gid
            params = params | any_params | int_params
        return sofmap_urlgenerate.build_search_url(**params)

    def _extract_params(
        self,
        options: dict,
        target_keys: list[str],
        convert_value: Callable | None = None,
    ) -> dict:
        if convert_value is None:
            return {k: v for k, v in options.items() if v and k in target_keys}
        return {
            k: convert_value(v) for k, v in options.items() if v and k in target_keys
        }
