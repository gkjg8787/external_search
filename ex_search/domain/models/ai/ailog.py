from sqlmodel import Field
from sqlalchemy import JSON, Column
from sqlalchemy.ext.mutable import MutableDict

from domain.models.base_model import SQLBase


class ParserGenerationLog(SQLBase, table=True):
    label: str = Field(index=True)
    target_url: str
    query: str
    response: dict = Field(
        default_factory=dict, sa_column=Column(MutableDict.as_mutable(JSON))
    )
    error_info: dict | None = Field(
        default=None, sa_column=Column(MutableDict.as_mutable(JSON(none_as_null=True)))
    )
    meta: dict = Field(
        default_factory=dict, sa_column=Column(MutableDict.as_mutable(JSON))
    )
