from common import read_config
from .web_scraper import (
    get_html_with_selenium as geo_download,
    GetCommandWithSelenium as GeoScrapeCommand,
)


async def async_download_geo(url: str):
    geo_opt = read_config.get_geo_options()
    selenium_opt = read_config.get_selenium_options()
    return await geo_download(
        command=GeoScrapeCommand(
            url=url,
            page_load_timeout=geo_opt.selenium.page_load_timeout,
            tag_wait_timeout=geo_opt.selenium.tag_wait_timeout,
            selenium_url=selenium_opt.remote_url,
        )
    )
