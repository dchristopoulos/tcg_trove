from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    reservation_id: int
    payment_method: str = Field(min_length=3, max_length=40)
    amount: int = Field(gt=0, le=1_000_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    payment_method: str
    amount: int
    currency: str
    status: str
    transaction_ref: str
    created_at: datetime
