from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PyObjectId


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1, max_length=2000)


class ReviewResponse(ReviewCreate):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    book_id: PyObjectId
    user_id: PyObjectId
    user_name: str | None = None
    book_title: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
