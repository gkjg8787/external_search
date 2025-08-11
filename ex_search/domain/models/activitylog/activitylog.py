from sqlmodel import Field
from sqlalchemy import JSON, Column
from sqlalchemy.ext.mutable import MutableDict

from domain.models.base_model import SQLBase
from . import enums


class ActivityLog(SQLBase, table=True):
    target_id: str
    target_table: str
    activity_type: str = Field(index=True)
    current_state: str = Field(default=enums.UpdateStatus.PENDING.name, index=True)
    caller_type: str
    meta: dict = Field(
        default_factory=dict, sa_column=Column(MutableDict.as_mutable(JSON))
    )
    error_msg: str = Field(default="")
