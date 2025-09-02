from pydantic import BaseModel, Field

from iosys.parser import SearchResultParser
from app.downloader import async_get


class GetCommandWithHttpx(BaseModel):
    url: str
    timout: float = 5
    delay_seconds: int = 1


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


async def parse_html(html: str, url: str):
    sparser = SearchResultParser(html_str=html, url=url)
    sparser.execute()
    return sparser.get_results()
