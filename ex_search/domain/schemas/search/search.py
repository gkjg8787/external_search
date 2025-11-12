from typing import Any, Optional
from pydantic import BaseModel, Field
from .constants import INIT_PAGE_LOAD_TIMEOUT, INIT_TAG_WAIT_TIMEOUT


class ErrorDetail(BaseModel):
    error_msg: str = ""
    error_type: str = ""


class Cookie(BaseModel):
    cookie_dict_list: Optional[list[dict[str, Any]]] = None
    return_cookies: Optional[bool] = False
    save: Optional[bool] = False
    load: Optional[bool] = False


class OnError(BaseModel):
    action_type: str = "raise"  # "raise" or "retry"
    max_retries: int = 0
    wait_time: float = 0.0  # seconds
    check_exist_tag: str = ""  # CSS selector


class WaitCSSSelector(BaseModel):
    selector: str
    timeout: Optional[int] = 10  # seconds
    on_error: Optional[OnError] = OnError()
    pre_wait_time: Optional[float] = 0.0  # seconds


class NodriverOptions(BaseModel):
    cookie: Optional[Cookie] = None
    wait_css_selector: Optional[WaitCSSSelector] = None
    page_wait_time: Optional[float] = None


class GeminiWaitOptions(BaseModel):
    wait_css_selector: str = ""
    page_load_timeout: int = Field(default=INIT_PAGE_LOAD_TIMEOUT, ge=2, le=100)
    tag_wait_timeout: int = Field(default=INIT_TAG_WAIT_TIMEOUT, ge=1, le=99)
    page_wait_time: float = Field(default=0, ge=0, le=30)


class PromptOptions(BaseModel):
    add_prompt: str = ""


class AskGeminiOptions(BaseModel, extra="ignore"):
    sitename: str = ""
    label: str = ""
    selenium: GeminiWaitOptions | None = None
    nodriver: NodriverOptions | None = None
    recreate_parser: bool = False
    exclude_script: bool = True
    compress_whitespace: bool = False
    prompt: PromptOptions | None = None


class IosysOptions(BaseModel):
    condition: str | None = None
    sort: str | None = None
    min_price: int | None = None
    max_price: int | None = None


class SofmapOptions(BaseModel):
    convert_to_direct_search: bool = False
    remove_duplicates: bool = True
    is_akiba: bool = False
    direct_search: bool = False
    product_type: str | None = None
    gid: str | None = None
    order_by: str | None = None
    category: str | None = None
    display_count: int | None = None


class SearchRequest(BaseModel):
    url: str | None = Field(default=None)
    search_keyword: str | None = Field(default=None)
    sitename: str
    options: SofmapOptions | IosysOptions | AskGeminiOptions | dict = Field(
        default_factory=dict
    )
    no_cache: bool = Field(default=False)


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


class DownloadRequest(BaseModel):
    url: str
    sitename: str
    options: SofmapOptions | IosysOptions | AskGeminiOptions | dict = Field(
        default_factory=dict
    )
    no_cache: bool = Field(default=False)


class DownLoadResponse(BaseModel):
    value: str | None = Field(default=None)
    error_msg: str = Field(default="")
