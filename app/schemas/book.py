from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PyObjectId


class BookStatus(str, Enum):
    AVAILABLE = "available"
    BORROWED = "borrowed"


SUPPORTED_GENRES = (
    "Fiction",
    "Non-fiction",
    "Science",
    "History",
    "Fantasy",
    "Sci-Fi",
    "Poetry",
    "Management",
    "Mechanics",
    "Programming",
    "Economics",
    "Художня література",
    "Нон-фікшн",
    "Наука",
    "Історія",
    "Фентезі",
    "Наукова фантастика",
    "Поезія",
    "Менеджмент",
    "Механіка",
    "Програмування",
    "Економіка",
)


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=160)
    description: str = ""
    genre: str = Field(min_length=1, max_length=80)
    cover_image_url: str | None = None


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    genre: str | None = Field(default=None, min_length=1, max_length=80)
    cover_image_url: str | None = None


class BookResponse(BookBase):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    rating: float = Field(default=0.0, ge=0.0, le=5.0)
    status: BookStatus = BookStatus.AVAILABLE
    current_reader_id: PyObjectId | None = None
    return_deadline: datetime | None = None
    queue: list[PyObjectId] = Field(default_factory=list)
    reserved_for_user_id: PyObjectId | None = None
    reservation_expires_at: datetime | None = None
