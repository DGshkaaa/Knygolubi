from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import database_dependency, get_current_user
from app.api.books import parse_object_id
from app.schemas.review import ReviewCreate, ReviewResponse
from app.schemas.user import UserInDatabase, UserRole


router = APIRouter(prefix="/api/books/{book_id}/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewResponse])
async def list_reviews(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> list[ReviewResponse]:
    object_id = parse_object_id(book_id)
    if await database.books.find_one({"_id": object_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    book = await database.books.find_one({"_id": object_id}, {"title": 1})
    reviews = []
    async for review in database.reviews.find({"book_id": object_id}).sort("created_at", -1):
        user = await database.users.find_one({"_id": review["user_id"]}, {"name": 1, "email": 1})
        review["user_name"] = (user or {}).get("name") or (user or {}).get("email")
        review["book_title"] = book.get("title") if book else None
        reviews.append(ReviewResponse.model_validate(review))
    return reviews


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    book_id: str,
    payload: ReviewCreate,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> ReviewResponse:
    object_id = parse_object_id(book_id)
    if await database.books.find_one({"_id": object_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    if await database.reviews.find_one({"book_id": object_id, "user_id": current_user.id}) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ви вже залишали відгук на цю книгу")

    review = {
        "book_id": object_id,
        "user_id": current_user.id,
        "rating": payload.rating,
        "comment": payload.comment,
        "created_at": datetime.now(timezone.utc),
    }
    result = await database.reviews.insert_one(review)
    review["_id"] = result.inserted_id
    ratings = [item["rating"] async for item in database.reviews.find({"book_id": object_id}, {"rating": 1})]
    await database.books.update_one({"_id": object_id}, {"$set": {"rating": round(sum(ratings) / len(ratings), 1)}})
    review["user_name"] = current_user.name or current_user.email
    review["book_title"] = (await database.books.find_one({"_id": object_id}, {"title": 1})).get("title")
    return ReviewResponse.model_validate(review)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    book_id: str,
    review_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> None:
    book_object_id = parse_object_id(book_id)
    review_object_id = parse_object_id(review_id)
    review = await database.reviews.find_one({"_id": review_object_id, "book_id": book_object_id})
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Відгук не знайдено")
    is_staff = current_user.role in {UserRole.ADMIN, UserRole.MODERATOR}
    if review.get("user_id") != current_user.id and not is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ви можете видаляти лише власні відгуки")

    result = await database.reviews.delete_one({"_id": review_object_id, "book_id": book_object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ваш відгук не знайдено")

    ratings = [item["rating"] async for item in database.reviews.find({"book_id": book_object_id}, {"rating": 1})]
    new_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    await database.books.update_one({"_id": book_object_id}, {"$set": {"rating": new_rating}})
