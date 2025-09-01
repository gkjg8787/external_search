from pydantic import BaseModel, Field
from .constants import NONE_PRICE, IOSYS


class ParseResult(BaseModel):
    title: str = ""
    price: int = NONE_PRICE
    condition: str = ""
    on_sale: bool = False
    salename: str = ""
    is_success: bool = False
    url: str = ""
    sitename: str = IOSYS
    image_url: str = ""
    category: str = ""
    manufacturer: str = ""
    release_date: str = ""
    accessories: str = ""
    stock_quontity: str = ""
    sub_infos: dict = Field(default_factory=dict)
    detail_url: str = ""


class ParseResults(BaseModel):
    results: list[ParseResult] = Field(default_factory=list)
