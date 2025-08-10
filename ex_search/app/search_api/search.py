from typing import Callable
from urllib.parse import urlparse
from enum import Enum
from datetime import datetime, timezone, timedelta
import uuid
import time
import asyncio

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from common import read_config
from domain.schemas.search import SearchRequest, SearchResponse
from domain.models.cache import cache as c_cache, command as c_cmd, enums as c_enums
from databases.sql.cache import repository as c_repo
from domain.models.activitylog import enums as act_enums
from app.sofmap.web_scraper import (
    get_html as sofmap_download,
    parse_html as parse_sofmap,
    ScrapeCommand as SofmapScrapeCommand,
    is_akiba_sofmap,
)
from app.sofmap.model_convert import ModelConverter
from app.sofmap import urlgenerate as sofmap_urlgenerate, category as sofmap_category
from app.activitylog.update import UpdateActivityLog
from app.activitylog.util import is_updating_url
from . import error as search_err


class SuppoertedDomain(Enum):
    SOFMAP = "www.sofmap.com"
    A_SOFMAP = "a.sofmap.com"


class SupportedSiteName(Enum):
    SOFMAP = "sofmap"


class ActivityName(Enum):
    SearchClient = "searchclient"


async def wait_until_activitylog_is_available(
    fastapireq: Request,
    upactlog: UpdateActivityLog,
    activity_types: list[str] = [],
    target_table: str = "",
    wait_time: float = 1.5,
    timeout: float = 10,
):
    start_time = time.perf_counter()
    while not await is_updating_url(
        updateactlog=upactlog,
        activity_types=activity_types,
        target_table=target_table,
    ):
        if await fastapireq.is_disconnected():
            return False, "Task cancelled by client"
        if timeout < time.perf_counter() - start_time:
            return False, "timeout"
        await asyncio.sleep(wait_time)

    return True, ""


class SearchClient:
    session: AsyncSession
    fastapirequest: Request
    searchrequest: SearchRequest
    caller_type: str

    def __init__(
        self,
        ses: AsyncSession,
        request: Request,
        searchrequest: SearchRequest,
        caller_type: str = "",
    ):
        self.session = ses
        self.fastapirequest = request
        self.searchrequest = searchrequest
        self.caller_type = caller_type

    async def _wait_create_activitylog(
        self, upactlog: UpdateActivityLog, target_table: str, retry: int = 6
    ):
        retry_cnt = 0
        while True:
            ok, msg = await wait_until_activitylog_is_available(
                fastapireq=self.fastapirequest,
                upactlog=upactlog,
                activity_types=[ActivityName.SearchClient.value],
                target_table=target_table,
            )
            if ok:
                tasklog = await upactlog.create(
                    target_id=str(uuid.uuid4()),
                    target_table=target_table,
                    activity_type=ActivityName.SearchClient.value,
                    caller_type=self.caller_type,
                )
                if tasklog:
                    return tasklog, ""
            elif await self.fastapirequest.is_disconnected():
                raise search_err.DisconnectedError(
                    "Client disconnected, canceling task"
                )
            else:
                retry_cnt += 1
                if retry < retry_cnt:
                    raise search_err.RetryError(
                        f"retry count max to create activitylog : {retry}"
                    )
                continue

    async def execute(self) -> SearchResponse:
        searchrequest: SearchRequest = self.searchrequest
        upactlog = UpdateActivityLog(ses=self.session)
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
                )
                return SearchResponse(error_msg=str(e))

        parsed_url = urlparse(searchrequest.url)
        try:
            tasklog, msg = await self._wait_create_activitylog(
                upactlog=upactlog,
                target_table=parsed_url.netloc,
            )
        except Exception as e:
            return SearchResponse(error_msg=str(e))
        if not tasklog:
            return SearchResponse(error_msg=str(msg))

        tasklog_id = tasklog.id
        ok, result = await self._download_html()
        if not ok:
            return SearchResponse(error_msg=result)

        match parsed_url.netloc:
            case SuppoertedDomain.SOFMAP.value | SuppoertedDomain.A_SOFMAP.value:
                parsed_result = await parse_sofmap(
                    html=result.download_text, url=searchrequest.url
                )
                sresults = ModelConverter.parseresults_to_searchresults(
                    results=parsed_result
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
                await self._set_search_cache(searchcache=result, expires=cache_expires)
        await upactlog.completed(id=tasklog_id)
        return response

    async def _get_search_cache(self) -> c_cache.SearchCache | None:
        repo = c_repo.SearchCacheRepository(ses=self.ses)
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
        expires: datetime,
    ):
        searchcache.expires = expires
        repo = c_repo.SearchCacheRepository(ses=self.ses)
        await repo.save(data=searchcache)

    async def _download_html(self):
        searchrequest = self.searchrequest
        parsed_url = urlparse(searchrequest.url)
        searchcache = await self._get_search_cache()
        if not searchcache and searchcache.download_text:
            return True, searchcache
        else:
            seleniumopt = read_config.get_selenium_options()
            match parsed_url.netloc:
                case SuppoertedDomain.SOFMAP.value | SuppoertedDomain.A_SOFMAP.value:
                    sofmapopt = read_config.get_sofmap_options()
                    ok, result = await sofmap_download(
                        command=SofmapScrapeCommand(
                            url=searchrequest.url,
                            is_ucaa=is_akiba_sofmap(searchrequest.url),
                            async_session=self.session,
                            page_load_timeout=sofmapopt.selenium.page_load_timeout,
                            tag_wait_timeout=sofmapopt.selenium.tag_wait_timeout,
                            selenium_url=seleniumopt.remote_url,
                        )
                    )
                    searchcache = c_cache.SearchCache(
                        domain=parsed_url.netloc,
                        url=searchrequest.url,
                        download_type=c_enums.DownloadType.SELENIUM.value,
                        download_text=result,
                    )
                    return ok, searchcache
                case _:
                    return False, f"not supported domain : {parsed_url.netloc}"
        return False, "not download"


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
                            ses=self.ses,
                            is_akiba=any_params.get("is_akiba", False),
                            category_name=category_name,
                        )
                        if gid:
                            any_params["gid"] = gid
                    params = any_params | int_params
                return sofmap_urlgenerate.build_search_url(**params)
            case _:
                raise ValueError(
                    f"not supported sitename : {searchrequest.sitename.lower()}"
                )

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
