from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.api.books import parse_object_id
from app.api.deps import database_dependency, require_moderator, require_staff
from app.schemas.book import BookStatus
from app.schemas.proposal import ProposalDecision, ProposalEdit, ProposalResponse, ProposalStatus
from app.schemas.user import UserInDatabase, UserResponse, UserRole


router = APIRouter(prefix="/api/moderation", tags=["moderation"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_moderator)],
) -> list[UserResponse]:
    return [
        UserResponse.model_validate(user)
        async for user in database.users.find({}, {"password_hash": 0}).sort("name", 1)
    ]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    role: UserRole,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    moderator: Annotated[UserInDatabase, Depends(require_moderator)],
) -> UserResponse:
    object_id = parse_object_id(user_id)
    if object_id == moderator.id or role == UserRole.MODERATOR:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Роль головного модератора не можна змінити тут")
    result = await database.users.update_one({"_id": object_id}, {"$set": {"role": role.value}})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")
    user = await database.users.find_one({"_id": object_id}, {"password_hash": 0})
    return UserResponse.model_validate(user)


@router.get("/proposals", response_model=list[ProposalResponse])
async def list_proposals(
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
) -> list[ProposalResponse]:
    return [
        ProposalResponse.model_validate(proposal)
        async for proposal in database.book_proposals.find().sort("created_at", -1)
    ]


@router.patch("/proposals/{proposal_id}", response_model=ProposalResponse)
async def decide_proposal(
    proposal_id: str,
    payload: ProposalDecision,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
) -> ProposalResponse:
    object_id = parse_object_id(proposal_id)
    proposal = await database.book_proposals.find_one({"_id": object_id})
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пропозицію не знайдено")
    if proposal.get("status") != ProposalStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пропозицію вже розглянуто")

    now = datetime.now(timezone.utc)
    if payload.status == ProposalStatus.APPROVED:
        await database.books.insert_one({
            "title": proposal["title"],
            "author": proposal["author"],
            "description": proposal.get("description", ""),
            "genre": proposal["genre"],
            "cover_image_url": proposal.get("cover_image_url"),
            "rating": 0.0,
            "status": BookStatus.AVAILABLE.value,
            "current_reader_id": None,
            "return_deadline": None,
            "queue": [],
            "reserved_for_user_id": None,
            "reservation_expires_at": None,
        })

    updated = await database.book_proposals.find_one_and_update(
        {"_id": object_id, "status": ProposalStatus.PENDING.value},
        {"$set": {
            "status": payload.status.value,
            "moderator_comment": payload.moderator_comment,
            "reviewed_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    decision = "схвалено" if payload.status == ProposalStatus.APPROVED else "відхилено"
    comment = f" {payload.moderator_comment}" if payload.moderator_comment else ""
    await database.users.update_one(
        {"_id": proposal["proposed_by"]},
        {"$push": {"notifications": {
            "message": f"Вашу пропозицію «{proposal['title']}» {decision}.{comment}",
            "is_read": False,
            "created_at": now,
        }}},
    )
    return ProposalResponse.model_validate(updated)


@router.patch("/proposals/{proposal_id}/edit", response_model=ProposalResponse)
async def edit_proposal(
    proposal_id: str,
    payload: ProposalEdit,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
) -> ProposalResponse:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не вказано жодної зміни")
    result = await database.book_proposals.update_one(
        {"_id": parse_object_id(proposal_id), "status": ProposalStatus.PENDING.value},
        {"$set": changes},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пропозицію на розгляді не знайдено")
    proposal = await database.book_proposals.find_one({"_id": parse_object_id(proposal_id)})
    return ProposalResponse.model_validate(proposal)
