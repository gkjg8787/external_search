from typing import Literal
from pydantic import BaseModel, Field


class AskGeminiErrorInfo(BaseModel):
    error_type: str
    error: str


class ResultItem(BaseModel):
    title: str
    price: int
    condition: str
    on_sale: bool
    is_success: bool
    image_url: str
    stock_quantity: int = Field(default=0)
    point: int = Field(default=0)
    detail_url: str = Field(default="")
    others: dict = Field(default_factory=dict)


class ResultItems(BaseModel):
    items: list[ResultItem] = Field(default_factory=list)


class AskGeminiResult(BaseModel):
    parsed_result: ResultItems | None = None
    error_info: AskGeminiErrorInfo | None = None


class HTMLConfigSearchResult(BaseModel):
    search_results_displayed: Literal["displayed", "zero", "none", "error"] = Field(
        description="CSS selector to identify the section displaying search results"
    )
    search_results_selector: str = Field(
        description="CSS selector to identify individual search result items"
    )
    item_selector: str = Field(
        description="CSS selector to identify individual item within search results"
    )
    error_msg: str = Field(
        default="", description="Error message if any issues occur during the search"
    )
