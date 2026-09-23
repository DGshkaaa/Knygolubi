from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PyObjectId


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=3000)
    genre: str = Field(min_length=1, max_length=80)
    cover_image_url: str | None = None
    note: str = Field(default="", max_length=1000)


class ProposalResponse(ProposalCreate):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id")
    proposed_by: PyObjectId
    status: ProposalStatus = ProposalStatus.PENDING
    moderator_comment: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class ProposalDecision(BaseModel):
    status: ProposalStatus
    moderator_comment: str | None = Field(default=None, max_length=1000)


class ProposalEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=3000)
    genre: str | None = Field(default=None, min_length=1, max_length=80)
    cover_image_url: str | None = None
    note: str | None = Field(default=None, max_length=1000)
