from common import read_config
from .web_scraper import (
    get_html_with_selenium as sofmap_download,
    GetCommandWithSelenium as SofmapScrapeCommand,
)


async def async_download_sofmap(url: str):
    sofmapopt = read_config.get_sofmap_options()
    seleniumopt = read_config.get_selenium_options()
    searchopt = read_config.get_search_options()
    ok, result = await sofmap_download(
        command=SofmapScrapeCommand(
            url=url,
            is_ucaa=not searchopt.safe_search,
            page_load_timeout=sofmapopt.selenium.page_load_timeout,
            tag_wait_timeout=sofmapopt.selenium.tag_wait_timeout,
            selenium_url=seleniumopt.remote_url,
        )
    )
    return ok, result
