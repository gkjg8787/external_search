from pydantic import BaseModel, Field


class InfoRequest(BaseModel):
    sitename: str
    infoname: str
    options: dict


class CategoryInfo(BaseModel):
    gid: str
    name: str


class InfoResponse(BaseModel):
    results: list[CategoryInfo] = Field(default_factory=list)
    error_msg: str = Field(default="")
