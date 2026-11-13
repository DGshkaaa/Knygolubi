from datetime import datetime, timedelta, timezone
import re
from typing import Annotated
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.api.deps import database_dependency, require_approved_user
from app.schemas.board import (
    BoardMessageCreate, BoardThreadResponse, PostContent, PostKind, PostResponse, PostStatus,
)
from app.schemas.user import UserInDatabase, UserRole

router = APIRouter(prefix="/api/board", tags=["community board"])
Database = Annotated[AsyncIOMotorDatabase, Depends(database_dependency)]
Reader = Annotated[UserInDatabase, Depends(require_approved_user)]


def parse_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(400, "Некоректний ідентифікатор оголошення або розмови.")
    return ObjectId(value)


def public_post(document: dict) -> PostResponse:
    document = dict(document)
    expires = document["expires_at"].replace(tzinfo=timezone.utc)
    if document["status"] == "open" and expires <= datetime.now(timezone.utc):
        document["status"] = "expired"
    return PostResponse.model_validate(document)


async def get_post(database, post_id: str) -> dict:
    post = await database.board_posts.find_one({"_id": parse_object_id(post_id)})
    if post is None:
        raise HTTPException(404, "Оголошення видалено або не знайдено.")
    return post


async def ensure_post_limit(database, owner_id) -> None:
    count = await database.board_posts.count_documents({
        "owner_id": owner_id, "status": "open", "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if count >= 10:
        raise HTTPException(409, "Можна мати до 10 активних оголошень. Закрийте неактуальні.")


async def notify(database, recipient_id, post: dict, message: str) -> None:
    await database.users.update_one({"_id": recipient_id}, {"$push": {"notifications": {
        "notification_id": str(uuid4()), "type": "board_message", "board_post_id": post["_id"],
        "message": message, "is_read": False, "created_at": datetime.now(timezone.utc),
    }}})


async def posts_page(database, response, filters, search, kind, page, page_size):
    if search and search.strip():
        pattern = re.escape(search.strip())
        filters["$or"] = [{field: {"$regex": pattern, "$options": "i"}}
                          for field in ("book_title", "book_author", "description")]
    if kind:
        filters["kind"] = kind.value
    total = await database.board_posts.count_documents(filters)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Has-Next"] = str(page * page_size < total).lower()
    cursor = database.board_posts.find(filters).sort("created_at", -1).skip((page-1)*page_size).limit(page_size)
    return [public_post(post) async for post in cursor]


@router.get("", response_model=list[PostResponse])
async def list_posts(
    response: Response, database: Database,
    search: str | None = Query(default=None, max_length=200), kind: PostKind | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=9, ge=1, le=30),
):
    return await posts_page(database, response, {
        "status": "open", "expires_at": {"$gt": datetime.now(timezone.utc)},
    }, search, kind, page, page_size)


@router.get("/mine", response_model=list[PostResponse])
async def my_posts(
    response: Response, database: Database, reader: Reader,
    search: str | None = Query(default=None, max_length=200), kind: PostKind | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=9, ge=1, le=30),
):
    return await posts_page(database, response, {"owner_id": reader.id}, search, kind, page, page_size)


@router.post("", response_model=PostResponse, status_code=201)
async def create_post(payload: PostContent, database: Database, reader: Reader):
    await ensure_post_limit(database, reader.id)
    now = datetime.now(timezone.utc)
    document = {
        **payload.model_dump(mode="json"), "owner_id": reader.id, "owner_name": reader.name,
        "status": "open", "created_at": now, "expires_at": now + timedelta(days=30),
    }
    await database.board_posts.insert_one(document)
    return public_post(document)


@router.get("/{post_id}", response_model=PostResponse)
async def post_detail(post_id: str, database: Database):
    return public_post(await get_post(database, post_id))


@router.put("/{post_id}", response_model=PostResponse)
async def edit_post(post_id: str, payload: PostContent, database: Database, reader: Reader):
    post = await get_post(database, post_id)
    if post["owner_id"] != reader.id:
        raise HTTPException(403, "Редагувати оголошення може лише його автор.")
    fields = payload.model_dump(mode="json")
    await database.board_posts.update_one({"_id": post["_id"]}, {"$set": fields})
    return public_post({**post, **fields})


@router.patch("/{post_id}/status", response_model=PostResponse)
async def change_status(post_id: str, payload: PostStatus, database: Database, reader: Reader):
    post = await get_post(database, post_id)
    if post["owner_id"] != reader.id:
        raise HTTPException(403, "Змінювати статус може лише автор оголошення.")
    fields = {"status": payload.status}
    if payload.status == "open" and public_post(post).status != "open":
        await ensure_post_limit(database, reader.id)
        fields["expires_at"] = datetime.now(timezone.utc) + timedelta(days=30)
    await database.board_posts.update_one({"_id": post["_id"]}, {"$set": fields})
    return public_post({**post, **fields})


@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: str, database: Database, reader: Reader):
    post = await get_post(database, post_id)
    if post["owner_id"] != reader.id and reader.role not in {UserRole.ADMIN, UserRole.MODERATOR}:
        raise HTTPException(403, "Видалити оголошення може автор або модератор.")
    await database.board_posts.delete_one({"_id": post["_id"]})
    await database.board_threads.delete_many({"post_id": post["_id"]})


@router.get("/{post_id}/responses", response_model=list[BoardThreadResponse])
async def list_responses(post_id: str, database: Database, reader: Reader):
    post = await get_post(database, post_id)
    filters = {"post_id": post["_id"]}
    if post["owner_id"] != reader.id:
        filters["responder_id"] = reader.id
    return [BoardThreadResponse.model_validate(thread) async for thread in
            database.board_threads.find(filters).sort("updated_at", -1)]


@router.post("/{post_id}/responses", response_model=BoardThreadResponse, status_code=201)
async def respond(post_id: str, payload: BoardMessageCreate, database: Database, reader: Reader):
    post = await get_post(database, post_id)
    if post["owner_id"] == reader.id:
        raise HTTPException(400, "Це ваше оголошення. Відгуки читачів з’являться нижче.")
    if public_post(post).status != "open":
        raise HTTPException(409, "Оголошення вже неактуальне. Нові відгуки закрито.")
    now = datetime.now(timezone.utc)
    document = {
        "post_id": post["_id"], "owner_id": post["owner_id"], "responder_id": reader.id,
        "responder_name": reader.name, "updated_at": now,
        "messages": [{"sender_id": reader.id, "text": payload.text, "created_at": now}],
    }
    try:
        await database.board_threads.insert_one(document)
    except DuplicateKeyError as error:
        raise HTTPException(409, "Ви вже відгукнулися. Продовжіть розмову нижче.") from error
    await notify(database, post["owner_id"], post, f"{reader.name} відгукнувся на «{post['book_title']}».")
    return BoardThreadResponse.model_validate(document)


@router.post("/threads/{thread_id}/messages", response_model=BoardThreadResponse)
async def send_message(thread_id: str, payload: BoardMessageCreate, database: Database, reader: Reader):
    thread = await database.board_threads.find_one({"_id": parse_object_id(thread_id)})
    if thread is None:
        raise HTTPException(404, "Розмову не знайдено.")
    if reader.id not in {thread["owner_id"], thread["responder_id"]}:
        raise HTTPException(403, "Цю розмову бачать лише її учасники.")
    post = await get_post(database, str(thread["post_id"]))
    now = datetime.now(timezone.utc)
    message = {"sender_id": reader.id, "text": payload.text, "created_at": now}
    result = await database.board_threads.update_one(
        {"_id": thread["_id"], "messages.49": {"$exists": False}},
        {"$push": {"messages": message}, "$set": {"updated_at": now}},
    )
    if result.modified_count == 0:
        raise HTTPException(409, "У розмові вже 50 повідомлень. Узгодьте подальший зв’язок з учасником.")
    recipient = thread["responder_id"] if reader.id == thread["owner_id"] else thread["owner_id"]
    await notify(database, recipient, post, f"Нове повідомлення від {reader.name} щодо «{post['book_title']}».")
    # Read back after the atomic append so parallel messages are not lost in UI.
    return BoardThreadResponse.model_validate(await database.board_threads.find_one({"_id": thread["_id"]}))
