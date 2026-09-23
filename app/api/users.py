from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.books import parse_object_id
from app.api.deps import database_dependency, get_current_user
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.schemas.review import ReviewResponse
from app.schemas.user import UserInDatabase


router = APIRouter(prefix="/api/users", tags=["profiles"])


def serialize_ids(values: list[ObjectId] | None) -> list[ObjectId]:
    return values or []


async def books_for_ids(database: AsyncIOMotorDatabase, ids: list[ObjectId]) -> list[dict]:
    if not ids:
        return []
    books = {
        book["_id"]: book
        async for book in database.books.find({"_id": {"$in": ids}})
    }
    return [books[book_id] for book_id in ids if book_id in books]


async def reviews_for_user(database: AsyncIOMotorDatabase, user_id: ObjectId) -> list[ReviewResponse]:
    reviews = []
    async for review in database.reviews.find({"user_id": user_id}).sort("created_at", -1):
        book = await database.books.find_one({"_id": review["book_id"]}, {"title": 1})
        review["user_name"] = None
        review["book_title"] = (book or {}).get("title")
        reviews.append(ReviewResponse.model_validate(review))
    return reviews


async def build_profile(database: AsyncIOMotorDatabase, user: dict) -> ProfileResponse:
    user_id = user["_id"]
    currently_reading = await database.books.find({"current_reader_id": user_id}).to_list(length=None)
    want_to_read = await database.books.find({"queue": user_id}).to_list(length=None)
    favorite_ids = user.get("favorites", user.get("wishlist_books", []))
    unfinished_ids = user.get("unfinished_books", user.get("abandoned_books", []))
    return ProfileResponse.model_validate({
        "_id": user_id,
        "name": user["name"],
        "email": user["email"],
        "role": user.get("role", "student"),
        "avatar_url": user.get("avatar_url"),
        "currently_reading": currently_reading,
        "want_to_read_books": want_to_read,
        "favorites": await books_for_ids(database, serialize_ids(favorite_ids)),
        "read_books": await books_for_ids(database, serialize_ids(user.get("read_books"))),
        "unfinished_books": await books_for_ids(database, serialize_ids(unfinished_ids)),
        "returned_books": await books_for_ids(database, serialize_ids(user.get("returned_books"))),
        "reviews": await reviews_for_user(database, user_id),
        "joined_at": user.get("joined_at"),
    })


@router.get("/me/profile", response_model=ProfileResponse)
async def my_profile(
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> ProfileResponse:
    user = await database.users.find_one({"_id": current_user.id})
    return await build_profile(database, user)


@router.put("/me/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> ProfileResponse:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes provided")
    await database.users.update_one({"_id": current_user.id}, {"$set": changes})
    user = await database.users.find_one({"_id": current_user.id})
    return await build_profile(database, user)


@router.get("/{user_id}/profile", response_model=ProfileResponse)
async def public_profile(
    user_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> ProfileResponse:
    user = await database.users.find_one({"_id": parse_object_id(user_id)})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await build_profile(database, user)


@router.post("/me/favorites/{book_id}")
async def toggle_favorite(
    book_id: str,
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> dict[str, bool]:
    object_id = parse_object_id(book_id)
    if await database.books.find_one({"_id": object_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    existing = await database.users.find_one({"_id": current_user.id, "favorites": object_id}, {"_id": 1})
    if existing:
        await database.users.update_one({"_id": current_user.id}, {"$pull": {"favorites": object_id}})
        return {"saved": False}
    await database.users.update_one({"_id": current_user.id}, {"$addToSet": {"favorites": object_id}})
    return {"saved": True}
