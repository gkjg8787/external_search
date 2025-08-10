from datetime import datetime
from pydantic import BaseModel


class SearchCacheGetCommand(BaseModel):
    domain: str | None = None
    url: str | None = None
    expires_start: datetime | None = None
    is_error: bool = False


class SearchCacheDeleteCommand(BaseModel):
    domain: str | None = None
    expires_end: datetime | None = None
    is_error: bool | None = None
