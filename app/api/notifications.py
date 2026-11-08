from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import database_dependency, require_approved_user
from app.schemas.book import BookResponse
from app.schemas.user import NotificationResponse, UserInDatabase


router = APIRouter(prefix="/api/users/me", tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    current_user: Annotated[UserInDatabase, Depends(require_approved_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> list[NotificationResponse]:
    user = await database.users.find_one(
        {"_id": current_user.id},
        {"notifications": 1},
    )
    notifications = (user or {}).get("notifications", [])
    return [NotificationResponse.model_validate(notification) for notification in notifications]


@router.get("/borrowed", response_model=list[BookResponse])
async def get_borrowed_books(
    current_user: Annotated[UserInDatabase, Depends(require_approved_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> list[BookResponse]:
    return [
        BookResponse.model_validate(book)
        async for book in database.books.find({"current_reader_id": current_user.id})
    ]


@router.patch("/notifications/read", status_code=204)
async def mark_notifications_read(
    current_user: Annotated[UserInDatabase, Depends(require_approved_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> None:
    await database.users.update_one(
        {"_id": current_user.id},
        {"$set": {"notifications.$[notification].is_read": True}},
        array_filters=[{"notification.is_read": False}],
    )
