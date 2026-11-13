from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global client, database
    client = AsyncIOMotorClient(settings.mongodb_url)
    database = client[settings.mongodb_database]
    await database.users.create_index("email", unique=True)
    await database.pending_registrations.create_index(
        "email_verification_expires_at", expireAfterSeconds=0
    )
    await database.pending_registrations.create_index("email_verification_token_hash", unique=True)
    await database.pending_registrations.create_index([("email", 1), ("created_at", -1)])
    await database.board_posts.create_index([("status", 1), ("expires_at", 1), ("created_at", -1)])
    await database.board_posts.create_index([("owner_id", 1), ("created_at", -1)])
    await database.board_threads.create_index([("post_id", 1), ("responder_id", 1)], unique=True)


async def close_mongo_connection() -> None:
    global client, database
    if client is not None:
        client.close()
    client = None
    database = None


def get_database() -> AsyncIOMotorDatabase:
    if database is None:
        raise RuntimeError("MongoDB connection has not been initialized")
    return database
