from datetime import datetime, timedelta, timezone
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.api.books import RESERVATION_HOURS, find_duplicate_book, normalize_isbn, parse_object_id
from app.core.notifications import notify_new_book
from app.api.deps import database_dependency, require_moderator, require_staff
from app.schemas.book import BookStatus
from app.schemas.proposal import ProposalDecision, ProposalEdit, ProposalResponse, ProposalStatus
from app.schemas.user import UserInDatabase, UserResponse, UserRole


router = APIRouter(prefix="/api/moderation", tags=["moderation"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    response: Response,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    search: str | None = Query(default=None, max_length=120),
) -> list[UserResponse]:
    filters: dict = {}
    if search and search.strip():
        pattern = re.escape(search.strip())
        filters["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"email": {"$regex": pattern, "$options": "i"}},
        ]
    total_count = await database.users.count_documents(filters)
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Has-Next"] = str(page * page_size < total_count).lower()
    users = []
    async for user in (
        database.users.find(filters, {"password_hash": 0})
        .sort("name", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    ):
        user.setdefault("email_verified", True)
        user.setdefault("is_approved", True)
        users.append(UserResponse.model_validate(user))
    return users


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    staff: Annotated[UserInDatabase, Depends(require_staff)],
) -> None:
    object_id = parse_object_id(user_id)
    if object_id == staff.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна видалити власний обліковий запис",
        )
    user = await database.users.find_one({"_id": object_id}, {"role": 1})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувача не знайдено",
        )
    if (
        user.get("role") in {UserRole.ADMIN.value, UserRole.MODERATOR.value}
        and staff.role != UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Видаляти облікові записи працівників може лише адміністратор",
        )

    affected_reviews = await database.reviews.find(
        {"user_id": object_id}, {"book_id": 1}
    ).to_list(length=None)
    affected_book_ids = {review["book_id"] for review in affected_reviews}
    await database.reviews.delete_many({"user_id": object_id})
    for book_id in affected_book_ids:
        ratings = [
            review["rating"]
            async for review in database.reviews.find(
                {"book_id": book_id}, {"rating": 1}
            )
        ]
        await database.books.update_one(
            {"_id": book_id},
            {"$set": {"rating": round(sum(ratings) / len(ratings), 1) if ratings else 0.0}},
        )

    async for book in database.books.find({"current_reader_id": object_id}):
        queue = [
            queued_user_id
            for queued_user_id in book.get("queue", [])
            if queued_user_id != object_id
        ]
        next_reader_id = queue.pop(0) if queue else None
        now = datetime.now(timezone.utc)
        await database.books.update_one(
            {"_id": book["_id"], "current_reader_id": object_id},
            {
                "$set": {
                    "status": BookStatus.AVAILABLE.value,
                    "current_reader_id": None,
                    "return_deadline": None,
                    "queue": queue,
                    "reserved_for_user_id": next_reader_id,
                    "reservation_expires_at": (
                        now + timedelta(hours=RESERVATION_HOURS)
                        if next_reader_id
                        else None
                    ),
                }
            },
        )
    await database.books.update_many(
        {"queue": object_id},
        {"$pull": {"queue": object_id}},
    )
    await database.books.update_many(
        {"reserved_for_user_id": object_id},
        {
            "$set": {"reserved_for_user_id": None},
            "$unset": {"reservation_expires_at": ""},
        },
    )
    await database.book_proposals.delete_many({"proposed_by": object_id})
    await database.users.delete_one({"_id": object_id})


@router.patch("/users/{user_id}/approval", response_model=UserResponse)
async def update_user_approval(
    user_id: str,
    is_approved: bool,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    staff: Annotated[UserInDatabase, Depends(require_staff)],
) -> UserResponse:
    object_id = parse_object_id(user_id)
    if object_id == staff.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна змінити власний статус підтвердження",
        )
    user = await database.users.find_one({"_id": object_id})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")
    if user.get("role") in {UserRole.ADMIN.value, UserRole.MODERATOR.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Статус працівників платформи змінювати тут не можна",
        )
    if is_approved and not user.get(
        "email_verified",
        True,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Користувач має спочатку підтвердити електронну пошту",
        )
    await database.users.update_one(
        {"_id": object_id},
        {"$set": {"is_approved": is_approved}},
    )
    updated_user = await database.users.find_one(
        {"_id": object_id}, {"password_hash": 0}
    )
    return UserResponse.model_validate(updated_user)


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
        duplicate = await find_duplicate_book(
            database, proposal["title"], proposal["author"], proposal.get("isbn")
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Книга «{duplicate['title']}» автора {duplicate['author']} вже є в каталозі.",
            )
        book_document = {
            "title": proposal["title"],
            "author": proposal["author"],
            "isbn": proposal.get("isbn"),
            "isbn_normalized": normalize_isbn(proposal.get("isbn")),
            "description": proposal.get("description", ""),
            "genre": proposal["genre"],
            "cover_image_url": proposal.get("cover_image_url"),
            "rating": 0.0,
            "views": 0,
            "published_at": now,
            "status": BookStatus.AVAILABLE.value,
            "current_reader_id": None,
            "return_deadline": None,
            "queue": [],
            "reserved_for_user_id": None,
            "reservation_expires_at": None,
        }
        result = await database.books.insert_one(book_document)
        book_document["_id"] = result.inserted_id
        await notify_new_book(database, book_document)

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
