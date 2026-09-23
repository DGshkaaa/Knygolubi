from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import decode_access_token
from app.db.mongo import get_database
from app.schemas.user import UserInDatabase, UserRole
from bson import ObjectId


bearer_scheme = HTTPBearer()


def database_dependency() -> AsyncIOMotorDatabase:
    return get_database()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    database: Annotated[AsyncIOMotorDatabase, Depends(database_dependency)],
) -> UserInDatabase:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не вдалося перевірити облікові дані",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
        user = await database.users.find_one({"_id": ObjectId(user_id)})
    except (InvalidTokenError, TypeError, ValueError):
        raise credentials_exception from None
    if user is None:
        raise credentials_exception
    return UserInDatabase.model_validate(user)


async def require_admin(
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> UserInDatabase:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Потрібні права адміністратора",
        )
    return current_user


async def require_moderator(
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> UserInDatabase:
    if current_user.role != UserRole.MODERATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Потрібні права модератора",
        )
    return current_user


async def require_staff(
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> UserInDatabase:
    if current_user.role not in {UserRole.ADMIN, UserRole.MODERATOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Потрібні права працівника платформи",
        )
    return current_user
