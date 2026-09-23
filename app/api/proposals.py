from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.books import parse_object_id
from app.api.deps import database_dependency, get_current_user
from app.schemas.proposal import ProposalCreate, ProposalResponse, ProposalStatus
from app.schemas.user import UserInDatabase


router = APIRouter(prefix="/api/proposals", tags=["proposals"])


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    payload: ProposalCreate,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> ProposalResponse:
    proposal = {
        **payload.model_dump(),
        "proposed_by": current_user.id,
        "status": ProposalStatus.PENDING.value,
        "moderator_comment": None,
        "created_at": datetime.now(timezone.utc),
        "reviewed_at": None,
    }
    result = await database.book_proposals.insert_one(proposal)
    proposal["_id"] = result.inserted_id
    return ProposalResponse.model_validate(proposal)


@router.get("/mine", response_model=list[ProposalResponse])
async def list_my_proposals(
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> list[ProposalResponse]:
    return [
        ProposalResponse.model_validate(proposal)
        async for proposal in database.book_proposals.find({"proposed_by": current_user.id}).sort("created_at", -1)
    ]
