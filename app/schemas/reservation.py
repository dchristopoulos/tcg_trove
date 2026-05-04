from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.status import ReservationStatus


class ReservationCreate(BaseModel):
    listing_id: int
    start_date: date
    end_date: date


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    listing_id: int
    start_date: date
    end_date: date
    status: ReservationStatus
    total_price: int
    created_at: datetime
