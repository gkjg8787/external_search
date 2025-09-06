from pydantic import BaseModel, Field
from .constants import INIT_PAGE_LOAD_TIMEOUT, INIT_TAG_WAIT_TIMEOUT


class GeminiSeleniumOptions(BaseModel):
    use_selenium: bool = False
    wait_css_selector: str = ""
    page_load_timeout: int = Field(default=INIT_PAGE_LOAD_TIMEOUT, ge=2, le=100)
    tag_wait_timeout: int = Field(default=INIT_TAG_WAIT_TIMEOUT, ge=1, le=99)
    page_wait_time: float = Field(default=0, ge=0, le=30)


class AskGeminiOptions(BaseModel, extra="ignore"):
    sitename: str = ""
    label: str = ""
    selenium: GeminiSeleniumOptions | None = None
    recreate_parser: bool = False


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
