from datetime import datetime
from sqlmodel import Field

from domain.models.base_model import SQLBase


class SearchCache(SQLBase, table=True):
    domain: str
    url: str
    download_type: str
    download_text: str = Field(default="")
    expires: datetime | None = Field(default=None)
    error_msg: str = Field(default="")
