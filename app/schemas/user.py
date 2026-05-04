from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ALLOWED_ROLES = ("buyer", "seller", "supervisor", "admin")
UserRole = Literal["buyer", "seller", "supervisor", "admin"]


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "buyer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    role: UserRole
    must_reset_password: bool
    permission_grants: str | None = None
    permission_revokes: str | None = None
    email_verified: bool
    balance: int = 0


class UserPermissionUpdate(BaseModel):
    grants: list[str] = Field(default_factory=list)
    revokes: list[str] = Field(default_factory=list)

