from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from bs4 import BeautifulSoup

from app.downloader import download_remotely, async_get
from app.downloader import dl_with_nodriver_api as nodriver_api
from .ask_gemini import ParserGenerator
from .model_convert import ModelConverter
from domain.schemas.search import search
from domain.models.ai import repository as m_ia_repo
from databases.sql.ai import repository as ai_repo


class GetCommandWithSelenium(BaseModel):
    url: str
    page_load_timeout: int | None = None
    tag_wait_timeout: int | None = None
    selenium_url: str | None = None
    wait_css_selector: str = ""
    page_watit_time: int | None = None


class GetCommandWithHttpx(BaseModel):
    url: str
    timeout: float = 5
    delay_seconds: int = 1


class GetCommandWithNodriver(GetCommandWithHttpx):
    url: str
    timeout: float = 30
    delay_seconds: int = 2
    nodriver_options: search.NodriverOptions = search.NodriverOptions()
    max_retries: int = 0


async def get_html_with_nodriver_api(command: GetCommandWithNodriver):
    try:
        result = await nodriver_api.get_from_nodriver_api(
            url=command.url,
            nodriver_options=command.nodriver_options,
            timeout=command.timeout,
            max_retries=command.max_retries,
            delay_seconds=command.delay_seconds,
        )
        if result.error.error_msg:
            return (
                False,
                f"nodriver api error, type:{result.error.error_type}, message:{result.error.error_msg}",
            )
        return True, result.result
    except Exception as e:
        return False, f"nodriver api exception, type:{type(e).__name__}, message:{e}"


async def get_html_with_selenium(command: GetCommandWithSelenium):
    params = {
        "url": command.url,
        "wait_css_selector": command.wait_css_selector,
    }
    if command.page_load_timeout:
        params["page_load_timeout"] = command.page_load_timeout
    if command.tag_wait_timeout:
        params["page_load_timeout"] = command.tag_wait_timeout
    if command.selenium_url:
        params["selenium_url"] = command.selenium_url
    if command.page_watit_time:
        params["page_wait_time"] = command.page_watit_time
    try:
        html = download_remotely(**params)
    except Exception as e:
        return (
            False,
            f"selenium download error, type:{type(e).__name__}, message:{e} , url:{command.url}",
        )
    return True, html


async def get_html(command: GetCommandWithHttpx):
    try:
        result = await async_get(
            url=command.url,
            timeout=command.timeout,
            delay_seconds=command.delay_seconds,
        )
        return True, result
    except Exception as e:
        return False, f"download error, type:{type(e).__name__}, message:{e}"


def exclude_script_tags(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.decompose()
    return str(soup)


def compress_whitespace_in_html(html: str) -> str:
    return " ".join(html.split())


async def _parse_html(
    html: str,
    url: str,
    label: str,
    session: AsyncSession,
    pg_repository: m_ia_repo.IParserGenerationLogRepository,
    recreate: bool = False,
    exclude_script: bool = True,
    compress_whitespace: bool = False,
):
    if exclude_script:
        html = exclude_script_tags(html)
    if compress_whitespace:
        html = compress_whitespace_in_html(html)
    sparser = ParserGenerator(
        html_str=html,
        label=label,
        session=session,
        parserlog_repository=pg_repository,
        url=url,
        recreate=recreate,
    )
    result = await sparser.execute()
    return result.parsed_result


async def parse_html_and_convert(
    html: str,
    url: str,
    label: str,
    session: AsyncSession,
    sitename: str = "",
    remove_duplicates: bool = True,
    recreate: bool = False,
    exclude_script: bool = True,
    compress_whitespace: bool = False,
) -> search.SearchResults | None:
    parsed_result = await _parse_html(
        html=html,
        url=url,
        label=label,
        session=session,
        pg_repository=ai_repo.ParserGenerationLogRepository(session),
        recreate=recreate,
        exclude_script=exclude_script,
        compress_whitespace=compress_whitespace,
    )
    if not parsed_result:
        return None
    searchresults = ModelConverter.resultitems_to_searchresults(
        results=parsed_result,
        sitename=sitename,
        url=url,
        remove_duplicates=remove_duplicates,
    )
    return searchresults
