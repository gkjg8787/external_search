from pydantic import BaseModel, Field


class DownloadConfigGenerateRequest(BaseModel):
    url: str
    search_keyword: str
    timeout: int | None = Field(default=None)
    optimize: bool = Field(default=False)
    init_nodriver_page_wait_time: int | None = Field(default=None)
    strategy_order: list[str] | None = Field(
        default=None,
        description="HTMLセレクタの検出に使用する戦略の順序を指定します。例: ['ai', 'rule']",
    )


class DownloadConfigGenerateResponse(BaseModel):
    download_config: dict
    download_preset: dict
