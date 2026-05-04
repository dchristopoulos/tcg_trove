from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ViewingCreate(BaseModel):
    listing_id: int
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=480)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime) -> datetime:
        if value <= datetime.now(value.tzinfo):
            raise ValueError("scheduled_at must be in the future")
        return value


class ViewingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    listing_id: int
    scheduled_at: datetime
    duration_minutes: int
    status: str
    notes: str | None
