from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


async def notify_new_book(database: AsyncIOMotorDatabase, book: dict) -> None:
    notification = {
        "message": f"Нова книга: «{book['title']}» — {book['author']}",
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
        "type": "new_book",
        "book_id": book["_id"] if isinstance(book["_id"], ObjectId) else ObjectId(book["_id"]),
        "notification_id": str(uuid4()),
    }
    await database.users.update_many(
        {
            "email_verified": {"$ne": False},
            "is_approved": {"$ne": False},
        },
        {"$push": {"notifications": notification}},
    )
