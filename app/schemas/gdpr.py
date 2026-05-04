from pydantic import BaseModel


class GDPRUserExport(BaseModel):
    id: int
    email: str
    username: str
    role: str


class GDPRExportResponse(BaseModel):
    user: GDPRUserExport
    favorites: list[int]
    inquiries: list[int]
    inquiry_messages: list[int]
    reservations: list[int]


class DetailResponse(BaseModel):
    detail: str
