from urllib.parse import urlparse
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from databases.sql import util as db_util
from sofmap.parser import SearchResultParser
from . import cookie_util
from .constants import A_SOFMAP_NETLOC
from app.downloader import download


class ScrapeCommand(BaseModel):
    url: str
    is_ucaa: bool = Field(default=False)
    async_session: Any
    page_load_timeout: int | None = None
    tag_wait_timeout: int | None = None
    selenium_url: str | None = None


def is_akiba_sofmap(url: str) -> bool:
    parsed_url = urlparse(url)
    return A_SOFMAP_NETLOC == parsed_url.netloc


def is_valid_url_by_parse(url: str) -> bool:
    try:
        result = urlparse(url)
        return result.netloc and result.scheme
    except ValueError:
        return False


async def get_html(command: ScrapeCommand):
    if not is_valid_url_by_parse(command.url):
        return False, f"invalid url , url:{command.url}"
    is_a_sofmap = is_akiba_sofmap(command.url)
    cookie_dict_list = cookie_util.create_cookies(
        is_akiba=is_a_sofmap, is_ucaa=command.is_ucaa
    )
    params = {
        "url": command.url,
        "cookie_dict_list": cookie_dict_list,
        "wait_css_selector": ".product_list.flexcartbtn.ftbtn",
    }
    if command.page_load_timeout:
        params["page_load_timeout"] = command.page_load_timeout
    if command.tag_wait_timeout:
        params["page_load_timeout"] = command.tag_wait_timeout
    if command.selenium_url:
        params["selenium_url"] = command.selenium_url
    try:
        html = download.download_remotely(**params)
    except Exception as e:
        return False, f"download error, {e} , url:{command.url}"
    return True, html


async def parse_html(html: str, url: str):
    sparser = SearchResultParser(html_str=html, url=url)
    sparser.execute()
    return sparser.get_results()
