from typing import Annotated

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import database_dependency, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.user import UserCreate, UserInDatabase, UserResponse
from app.schemas.auth import LoginRequest, TokenResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> UserResponse:
    existing_user = await database.users.find_one({"email": payload.email.lower()})
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ця електронна пошта вже зареєстрована")

    user_document = {
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": "student",
        "notifications": [],
        "read_books": [],
        "abandoned_books": [],
        "unfinished_books": [],
        "returned_books": [],
        "favorites": [],
        "wishlist_books": [],
        "joined_at": datetime.now(timezone.utc),
    }
    result = await database.users.insert_one(user_document)
    user_document["_id"] = result.inserted_id
    return UserResponse.model_validate(user_document)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> TokenResponse:
    user = await database.users.find_one({"email": payload.email.lower()})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильна електронна пошта або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user["_id"]), user["role"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user.model_dump(by_alias=True))
