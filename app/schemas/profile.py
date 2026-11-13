from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.book import BookResponse
from app.schemas.common import PyObjectId
from app.schemas.review import ReviewResponse
from app.schemas.user import UserRole


class TelegramContact(BaseModel):
    telegram_username: str | None = Field(default=None, max_length=32)

    @field_validator("telegram_username", mode="before")
    @classmethod
    def normalize_telegram(cls, value):
        if value is None or not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            return None
        link = re.fullmatch(r"(?:https://)?(?:www\.)?t\.me/([A-Za-z][A-Za-z0-9_]{4,31})/?", value, re.IGNORECASE)
        if link:
            value = link.group(1)
        elif value.startswith("@"):
            value = value[1:]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", value):
            raise ValueError("Введіть Telegram-нік: 5–32 латинські літери, цифри або _, перший символ — літера. Наприклад, @book_reader.")
        return value.lower()


class ProfileUpdate(TelegramContact):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = None


class ProfileResponse(TelegramContact):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    name: str
    email: EmailStr | None = None
    role: UserRole
    email_verified: bool = True
    is_approved: bool = True
    avatar_url: str | None = None
    currently_reading: list[BookResponse] = Field(default_factory=list)
    want_to_read_books: list[BookResponse] = Field(default_factory=list)
    favorites: list[BookResponse] = Field(default_factory=list)
    read_books: list[BookResponse] = Field(default_factory=list)
    unfinished_books: list[BookResponse] = Field(default_factory=list)
    returned_books: list[BookResponse] = Field(default_factory=list)
    reviews: list[ReviewResponse] = Field(default_factory=list)
    joined_at: datetime | None = None
