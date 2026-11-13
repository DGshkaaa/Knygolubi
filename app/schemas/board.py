from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PyObjectId


class PostKind(str, Enum):
    WANTED = "wanted"
    EXCHANGE = "exchange"
    GIVEAWAY = "giveaway"


class PostContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PostKind
    book_title: str = Field(min_length=1, max_length=200)
    book_author: str = Field(default="", max_length=160)
    description: str = Field(min_length=10, max_length=2000)
    location: str = Field(default="", max_length=120)

    @field_validator("book_title", "book_author", "description", "location", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class PostStatus(BaseModel):
    status: str = Field(pattern="^(open|closed)$")


class PostResponse(PostContent):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    owner_id: PyObjectId
    owner_name: str
    status: str
    created_at: datetime
    expires_at: datetime


class BoardMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class BoardMessage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    sender_id: PyObjectId
    text: str
    created_at: datetime


class BoardThreadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    id: PyObjectId = Field(alias="_id")
    post_id: PyObjectId
    owner_id: PyObjectId
    responder_id: PyObjectId
    responder_name: str
    messages: list[BoardMessage]
    updated_at: datetime
