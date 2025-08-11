from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    url: str | None = Field(default=None)
    search_keyword: str | None = Field(default=None)
    sitename: str
    options: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    title: str | None = None
    price: int | None = None
    taxin: bool = False
    condition: str | None = None
    on_sale: bool = False
    salename: str | None = None
    is_success: bool = False
    url: str | None = None
    sitename: str | None = None
    image_url: str | None = None
    stock_msg: str | None = None
    stock_quantity: int | None = None
    sub_urls: list[str] | None = Field(default=None)
    shops_with_stock: str | None = None
    others: dict | None = Field(default=None)


class SearchResults(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)
    error_msg: str = Field(default="")


class SearchResponse(SearchResults):
    pass
