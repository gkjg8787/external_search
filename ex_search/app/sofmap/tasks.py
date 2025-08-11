from sqlalchemy.ext.asyncio import AsyncSession

from databases.sql import util as db_util
from common import read_config
from .web_scraper import (
    get_html as sofmap_download,
    is_akiba_sofmap,
    ScrapeCommand as SofmapScrapeCommand,
)


async def download_task(url: str):
    async for ses in db_util.get_async_session():
        return await async_download_sofmap(session=ses, url=url)


async def async_download_sofmap(session: AsyncSession, url: str):
    sofmapopt = read_config.get_sofmap_options()
    seleniumopt = read_config.get_selenium_options()
    ok, result = await sofmap_download(
        command=SofmapScrapeCommand(
            url=url,
            is_ucaa=is_akiba_sofmap(url),
            async_session=session,
            page_load_timeout=sofmapopt.selenium.page_load_timeout,
            tag_wait_timeout=sofmapopt.selenium.tag_wait_timeout,
            selenium_url=seleniumopt.remote_url,
        )
    )
    return ok, result
