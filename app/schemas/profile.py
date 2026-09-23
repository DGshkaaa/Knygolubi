from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.book import BookResponse
from app.schemas.common import PyObjectId
from app.schemas.review import ReviewResponse
from app.schemas.user import UserRole


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    name: str
    email: EmailStr
    role: UserRole
    avatar_url: str | None = None
    currently_reading: list[BookResponse] = Field(default_factory=list)
    want_to_read_books: list[BookResponse] = Field(default_factory=list)
    favorites: list[BookResponse] = Field(default_factory=list)
    read_books: list[BookResponse] = Field(default_factory=list)
    unfinished_books: list[BookResponse] = Field(default_factory=list)
    returned_books: list[BookResponse] = Field(default_factory=list)
    reviews: list[ReviewResponse] = Field(default_factory=list)
    joined_at: datetime | None = None