from pydantic import BaseModel

from app.downloader import download_remotely
from geo.parser import SearchResultParser


class GetCommandWithSelenium(BaseModel):
    url: str
    page_load_timeout: int | None = None
    tag_wait_timeout: int | None = None
    selenium_url: str | None = None


async def get_html_with_selenium(command: GetCommandWithSelenium):
    params = {
        "url": command.url,
        "wait_css_selector": "ul.itemList",
    }
    if command.page_load_timeout:
        params["page_load_timeout"] = command.page_load_timeout
    if command.tag_wait_timeout:
        params["page_load_timeout"] = command.tag_wait_timeout
    if command.selenium_url:
        params["selenium_url"] = command.selenium_url
    try:
        html = download_remotely(**params)
    except Exception as e:
        return False, f"download error, {e} , url:{command.url}"
    return True, html


async def parse_html(html: str, url: str):
    sparser = SearchResultParser(html_str=html, url=url)
    sparser.execute()
    return sparser.get_results()
