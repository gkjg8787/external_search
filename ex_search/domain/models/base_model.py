from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.orm import Mapper
from sqlmodel import Field, SQLModel


class SQLBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: bool = Field(default=False, index=True)

    @event.listens_for(Mapper, "before_update")
    def receive_before_update(mapper, connection, target):
        target.updated_at = datetime.now(timezone.utc)
