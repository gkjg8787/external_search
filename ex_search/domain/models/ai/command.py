from datetime import datetime

from pydantic import BaseModel


class ParserGenerationLogGetCommand(BaseModel):
    id: int | None = None
    label: str = ""
    target_url: str = ""
    updated_at_start: datetime | None = None
    updated_at_end: datetime | None = None
    is_error: bool | None = None
