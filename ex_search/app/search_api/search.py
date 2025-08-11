from typing import Callable
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import tasks as celery_tasks
from common import read_config
from domain.schemas.search import SearchRequest, SearchResponse
from domain.models.cache import cache as c_cache, command as c_cmd, enums as c_enums
from databases.sql.cache import repository as c_repo
from domain.models.activitylog import enums as act_enums
from app.sofmap.web_scraper import parse_html as parse_sofmap

from app.sofmap.model_convert import ModelConverter
from app.sofmap import urlgenerate as sofmap_urlgenerate, category as sofmap_category
from app.activitylog.update import UpdateActivityLog
from .enums import SuppoertedDomain, SupportedSiteName, ActivityName

DL_TIMEOUT = 60


class SearchClient:
    session: AsyncSession
    searchrequest: SearchRequest
    caller_type: str

    def __init__(
        self,
        ses: AsyncSession,
        searchrequest: SearchRequest,
        caller_type: str = "",
    ):
        self.session = ses
        self.searchrequest = searchrequest
        self.caller_type = caller_type

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
        tasklog = await upactlog.create(
            target_id=str(uuid.uuid4()),
            target_table=parsed_url.netloc,
            activity_type=ActivityName.SearchClient.value,
            caller_type=self.caller_type,
        )

        if not tasklog:
            return SearchResponse(error_msg=f"task is not created")

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
                result.expires = cache_expires
                await self._set_search_cache(searchcache=result)
        await upactlog.completed(id=tasklog_id)
        return response

    async def _get_search_cache(self) -> c_cache.SearchCache | None:
        repo = c_repo.SearchCacheRepository(ses=self.session)
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
        repo = c_repo.SearchCacheRepository(ses=self.session)
        await repo.save(data=searchcache)

    async def _download_html(self):
        searchrequest = self.searchrequest
        parsed_url = urlparse(searchrequest.url)
        searchcache = await self._get_search_cache()
        if searchcache and searchcache.download_text:
            return True, searchcache
        else:
            match parsed_url.netloc:
                case SuppoertedDomain.SOFMAP.value | SuppoertedDomain.A_SOFMAP.value:
                    dl_task = celery_tasks.sofmap_dl_task.delay(searchrequest.url)
                    ok, result = dl_task.get(timeout=DL_TIMEOUT)
                    if not ok:
                        return False, result
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
                            ses=self.session,
                            is_akiba=any_params.get("is_akiba", False),
                            category_name=category_name,
                        )
                        if gid:
                            any_params["gid"] = gid
                    params = params | any_params | int_params
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
