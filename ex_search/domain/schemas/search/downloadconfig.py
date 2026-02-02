from pydantic import BaseModel, Field


class DownloadConfigGenerateRequest(BaseModel):
    url: str
    search_keyword: str
    timeout: int | None = Field(default=None)
    optimize: bool = Field(default=True)
    init_nodriver_page_wait_time: int | None = Field(default=None)


class DownloadConfigGenerateResponse(BaseModel):
    download_config: dict
    download_preset: dict
