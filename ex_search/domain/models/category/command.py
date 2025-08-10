from pydantic import BaseModel


class CategoryGetCommand(BaseModel):
    id: int | None = None
    category_id: str = ""
    name: str = ""
    entity_type: str = ""
