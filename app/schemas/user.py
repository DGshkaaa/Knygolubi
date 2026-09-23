from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import PyObjectId


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"
    MODERATOR = "moderator"


class Notification(BaseModel):
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class UserInDatabase(UserBase):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    role: UserRole = UserRole.STUDENT
    password_hash: str
    avatar_url: str | None = None
    notifications: list[Notification] = Field(default_factory=list)
    read_books: list[PyObjectId] = Field(default_factory=list)
    abandoned_books: list[PyObjectId] = Field(default_factory=list)
    unfinished_books: list[PyObjectId] = Field(default_factory=list)
    returned_books: list[PyObjectId] = Field(default_factory=list)
    favorites: list[PyObjectId] = Field(default_factory=list)
    wishlist_books: list[PyObjectId] = Field(default_factory=list)


class UserResponse(UserBase):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    role: UserRole = UserRole.STUDENT
    avatar_url: str | None = None
    notifications: list[Notification] = Field(default_factory=list)


class NotificationResponse(Notification):
    pass
