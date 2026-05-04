from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.status import InquiryStatus


class InquiryCreate(BaseModel):
    listing_id: int
    message: str


class InquiryStatusUpdate(BaseModel):
    status: InquiryStatus


class InquiryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    listing_id: int
    message: str
    status: InquiryStatus
    created_at: datetime


class InquiryReplyCreate(BaseModel):
    body: str


class InquiryReplyRead(BaseModel):
    id: int
    inquiry_id: int
    sender_id: int
    sender_username: str | None = None
    body: str
    created_at: datetime
