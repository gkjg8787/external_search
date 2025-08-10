from datetime import datetime
from sqlmodel import Field

from domain.models.base_model import SQLBase


class Category(SQLBase, table=True):
    category_id: str = Field(index=True)
    name: str = Field(index=True)
    entity_type: str
