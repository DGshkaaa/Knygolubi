from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.books import router as books_router
from app.api.notifications import router as notifications_router
from app.api.reviews import router as reviews_router
from app.api.moderation import router as moderation_router
from app.api.proposals import router as proposals_router
from app.api.users import router as users_router
from app.core.config import settings
from app.db.mongo import close_mongo_connection, connect_to_mongo


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://knygolubi-1.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Has-Next"],
)
app.include_router(auth_router)
app.include_router(books_router)
app.include_router(notifications_router)
app.include_router(reviews_router)
app.include_router(moderation_router)
app.include_router(proposals_router)
app.include_router(users_router)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
