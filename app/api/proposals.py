from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.books import find_duplicate_book, parse_object_id
from app.api.deps import database_dependency, require_approved_user
from app.schemas.proposal import ProposalCreate, ProposalResponse, ProposalStatus
from app.schemas.user import UserInDatabase


router = APIRouter(prefix="/api/proposals", tags=["proposals"])


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    payload: ProposalCreate,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(require_approved_user)],
) -> ProposalResponse:
    duplicate = await find_duplicate_book(
        database, payload.title, payload.author, payload.isbn
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Книга «{duplicate['title']}» автора {duplicate['author']} вже є в каталозі.",
        )
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
    current_user: Annotated[UserInDatabase, Depends(require_approved_user)],
) -> list[ProposalResponse]:
    return [
        ProposalResponse.model_validate(proposal)
        async for proposal in database.book_proposals.find({"proposed_by": current_user.id}).sort("created_at", -1)
    ]
