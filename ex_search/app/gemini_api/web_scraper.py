from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession


from app.downloader import download_remotely, async_get
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
    timout: float = 5
    delay_seconds: int = 1


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
        return False, f"download error, {e} , url:{command.url}"
    return True, html


async def get_html(command: GetCommandWithHttpx):
    try:
        result = await async_get(
            url=command.url,
            timeout=command.timout,
            delay_seconds=command.delay_seconds,
        )
        return True, result
    except Exception as e:
        return False, str(e)


async def parse_html(
    html: str,
    url: str,
    label: str,
    session: AsyncSession,
    pg_repository: m_ia_repo.IParserGenerationLogRepository,
    recreate: bool = False,
):
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
) -> search.SearchResults | None:
    parsed_result = await parse_html(
        html=html,
        url=url,
        label=label,
        session=session,
        pg_repository=ai_repo.ParserGenerationLogRepository(session),
        recreate=recreate,
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
