from pydantic import BaseModel, Field
from .constants import NONE_PRICE, GEO


class ParseResult(BaseModel):
    title: str = ""
    price: int = NONE_PRICE
    condition: str = ""
    on_sale: bool = False
    salename: str = ""
    is_success: bool = False
    url: str = ""
    sitename: str = GEO
    image_url: str = ""
    category: str = ""
    stock_msg: str = ""
    detail_url: str = ""


class PageInfo(BaseModel):
    min_page: int = 0
    max_page: int = 0
    current_page: int = 0
    more_page: bool = False
    enable: bool = False


class ParseResults(BaseModel):
    results: list[ParseResult] = Field(default_factory=list)
    pageinfo: PageInfo | None = Field(default=None)
