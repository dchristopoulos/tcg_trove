from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SearchLogCreate(BaseModel):
    query: str
    filters: str = "{}"


class SearchLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    query: str
    filters: str
    created_at: datetime


class SearchSuggestionsRead(BaseModel):
    locations: list[str]
    property_types: list[str]
