from datetime import datetime, timedelta, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.api.deps import database_dependency, get_current_user, require_staff
from app.schemas.book import BookCreate, BookResponse, BookStatus, BookUpdate
from app.schemas.user import UserInDatabase


router = APIRouter(prefix="/api/books", tags=["books"])
BORROWING_DAYS = 14
RESERVATION_HOURS = 24


def serialize_book(book: dict) -> BookResponse:
    return BookResponse.model_validate(book)


def parse_object_id(book_id: str) -> ObjectId:
    if not ObjectId.is_valid(book_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некоректний ідентифікатор книги")
    return ObjectId(book_id)


@router.get("", response_model=list[BookResponse])
async def list_books(
    response: Response,
    search: str | None = None,
    genre: str | None = None,
    availability: BookStatus | None = None,
    sort_by: str | None = Query(default=None, pattern="^rating$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=50),
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> list[BookResponse]:
    filters: dict = {}
    if search:
        filters["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"author": {"$regex": search, "$options": "i"}},
        ]
    if genre:
        filters["genre"] = genre
    if availability:
        filters["status"] = availability.value

    total_count = await database.books.count_documents(filters)
    response.headers["X-Has-Next"] = str(page * page_size < total_count).lower()
    cursor = database.books.find(filters).skip((page - 1) * page_size).limit(page_size)
    if sort_by == "rating":
        cursor = cursor.sort("rating", -1)
    return [serialize_book(book) async for book in cursor]


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: str,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> BookResponse:
    book = await database.books.find_one({"_id": parse_object_id(book_id)})
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    return serialize_book(book)


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: BookCreate,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
) -> BookResponse:
    book_document = {
        **payload.model_dump(),
        "rating": 0.0,
        "status": BookStatus.AVAILABLE.value,
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    }
    result = await database.books.insert_one(book_document)
    book_document["_id"] = result.inserted_id
    return serialize_book(book_document)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: str,
    payload: BookUpdate,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
) -> BookResponse:
    object_id = parse_object_id(book_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не вказано жодної зміни")
    result = await database.books.update_one({"_id": object_id}, {"$set": changes})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    book = await database.books.find_one({"_id": object_id})
    return serialize_book(book)


@router.post("/{book_id}/borrow", response_model=BookResponse)
async def borrow_book(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> BookResponse:
    object_id = parse_object_id(book_id)
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=BORROWING_DAYS)
    reservation_filter = {
        "$or": [
            {"reserved_for_user_id": None},
            {"reserved_for_user_id": current_user.id},
            {"reservation_expires_at": {"$lt": now}},
        ]
    }
    result = await database.books.update_one(
        {"_id": object_id, "status": BookStatus.AVAILABLE.value, **reservation_filter},
        {
            "$set": {
                "status": BookStatus.BORROWED.value,
                "current_reader_id": current_user.id,
                "return_deadline": deadline,
                "reserved_for_user_id": None,
                "reservation_expires_at": None,
            }
        },
    )
    if result.matched_count == 0:
        book = await database.books.find_one({"_id": object_id})
        if book is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Книга зараз недоступна")
    return serialize_book(await database.books.find_one({"_id": object_id}))


@router.post("/{book_id}/queue", response_model=BookResponse)
async def queue_book(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> BookResponse:
    object_id = parse_object_id(book_id)
    book = await database.books.find_one({"_id": object_id})
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    if book.get("status") != BookStatus.BORROWED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Книга доступна для позичання")
    if book.get("current_reader_id") == current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Поточний читач не може вступити до черги")
    if current_user.id in book.get("queue", []):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ви вже перебуваєте в черзі")

    now = datetime.now(timezone.utc)
    update = {"$addToSet": {"queue": current_user.id}}
    updated_book = await database.books.find_one_and_update(
        {
            "_id": object_id,
            "status": BookStatus.BORROWED.value,
            "queue": {"$ne": current_user.id},
        },
        update,
        return_document=ReturnDocument.AFTER,
    )
    if updated_book is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Стан книги змінився. Спробуйте ще раз")

    reader_id = updated_book.get("current_reader_id")
    final_deadline = updated_book.get("return_deadline")
    await database.users.update_one(
        {"_id": reader_id},
        {
            "$push": {
                "notifications": {
                    "message": f"Хтось очікує на книгу «{updated_book['title']}». Будь ласка, поверніть її до {final_deadline.strftime('%d.%m.%Y о %H:%M')}",
                    "is_read": False,
                    "created_at": now,
                }
            }
        },
    )
    return serialize_book(updated_book)


@router.delete("/{book_id}/queue", response_model=BookResponse)
async def leave_queue(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> BookResponse:
    object_id = parse_object_id(book_id)
    result = await database.books.update_one(
        {"_id": object_id, "queue": current_user.id},
        {"$pull": {"queue": current_user.id}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ви не перебуваєте в черзі на цю книгу")
    return serialize_book(await database.books.find_one({"_id": object_id}))


@router.post("/{book_id}/return", response_model=BookResponse)
async def return_book(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
    finished: bool = True,
) -> BookResponse:
    object_id = parse_object_id(book_id)
    book = await database.books.find_one({"_id": object_id})
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    if book.get("status") != BookStatus.BORROWED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Книга зараз не позичена")
    if book.get("current_reader_id") != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Повернути книгу може лише поточний читач")

    queue = book.get("queue", [])
    now = datetime.now(timezone.utc)
    next_reader_id = queue[0] if queue else None
    reservation_expires_at = now + timedelta(hours=RESERVATION_HOURS) if next_reader_id else None
    update = {
        "$set": {
            "status": BookStatus.AVAILABLE.value,
            "current_reader_id": None,
            "return_deadline": None,
            "reserved_for_user_id": next_reader_id,
            "reservation_expires_at": reservation_expires_at,
        }
    }
    if queue:
        update["$pop"] = {"queue": -1}
    result = await database.books.update_one(
        {"_id": object_id, "status": BookStatus.BORROWED.value, "current_reader_id": current_user.id},
        update,
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Стан книги змінився. Спробуйте ще раз")

    updated_book = await database.books.find_one({"_id": object_id})
    if next_reader_id:
        await database.users.update_one(
            {"_id": next_reader_id},
            {
                "$push": {
                    "notifications": {
                        "message": f"Книга «{updated_book['title']}» доступна! У вас є 24 години, щоб її позичити.",
                        "is_read": False,
                        "created_at": now,
                    }
                }
            },
        )
    history_update = {"returned_books": object_id}
    history_update["read_books" if finished else "unfinished_books"] = object_id
    await database.users.update_one({"_id": current_user.id}, {"$addToSet": history_update})
    return serialize_book(updated_book)


@router.post("/{book_id}/abandon", response_model=BookResponse)
async def abandon_book(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> BookResponse:
    object_id = parse_object_id(book_id)
    book = await database.books.find_one({"_id": object_id})
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
    if book.get("current_reader_id") != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Позначити книгу недочитаною може лише поточний читач")
    queue = book.get("queue", [])
    next_reader_id = queue[0] if queue else None
    now = datetime.now(timezone.utc)
    update = {"$set": {"status": BookStatus.AVAILABLE.value, "current_reader_id": None, "return_deadline": None, "reserved_for_user_id": next_reader_id, "reservation_expires_at": now + timedelta(hours=RESERVATION_HOURS) if next_reader_id else None}}
    if queue:
        update["$pop"] = {"queue": -1}
    result = await database.books.update_one({"_id": object_id, "current_reader_id": current_user.id}, update)
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Стан книги змінився. Спробуйте ще раз")
    await database.users.update_one({"_id": current_user.id}, {"$addToSet": {"returned_books": object_id, "unfinished_books": object_id}})
    return serialize_book(await database.books.find_one({"_id": object_id}))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: str,
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
    _: Annotated[UserInDatabase, Depends(require_staff)],
) -> None:
    result = await database.books.delete_one({"_id": parse_object_id(book_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книгу не знайдено")
