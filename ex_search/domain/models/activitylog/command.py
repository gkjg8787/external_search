from datetime import datetime

from pydantic import BaseModel, Field


class ActivityLogGetCommand(BaseModel):
    id: int | None = None
    target_id: int | None = None
    target_table: str = ""
    activity_types: list[str] = Field(default_factory=list)
    current_states: list[str] = Field(default_factory=list)
    caller_type: str | None = None
    is_error: bool = False
    updated_at_start: datetime | None = None
    updated_at_end: datetime | None = None
