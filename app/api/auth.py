from typing import Annotated

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
import smtplib
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.api.deps import database_dependency, get_current_user
from app.core.email import email_is_configured, send_verification_email
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.user import UserCreate, UserInDatabase, UserResponse
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> MessageResponse:
    if not email_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Надсилання листів не налаштовано. Зверніться до адміністратора.",
        )

    existing_user = await database.users.find_one({"email": payload.email.lower()})
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ця електронна пошта вже зареєстрована")

    verification_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    user_document = {
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": "student",
        "email_verified": False,
        "is_approved": False,
        "email_verification_token_hash": hashlib.sha256(
            verification_token.encode("utf-8")
        ).hexdigest(),
        "email_verification_expires_at": now + timedelta(hours=24),
        "notifications": [],
        "read_books": [],
        "abandoned_books": [],
        "unfinished_books": [],
        "returned_books": [],
        "favorites": [],
        "wishlist_books": [],
        "joined_at": datetime.now(timezone.utc),
    }
    try:
        await database.users.insert_one(user_document)
    except DuplicateKeyError as error:
        raise HTTPException(status_code=409, detail="Ця електронна пошта вже зареєстрована") from error
    try:
        await send_verification_email(user_document["email"], verification_token)
    except (OSError, smtplib.SMTPException) as error:
        logger.error("Registration email delivery failed: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не вдалося надіслати лист підтвердження. Спробуйте повторити надсилання.",
        ) from error
    return MessageResponse(
        message="Перевірте пошту та перейдіть за посиланням для підтвердження адреси."
    )


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    payload: EmailVerificationRequest,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> MessageResponse:
    if not email_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Надсилання листів не налаштовано. Зверніться до адміністратора.",
        )

    user = await database.users.find_one({"email": payload.email.lower()})
    if user is not None and not user.get("email_verified", True):
        verification_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        await database.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "email_verification_token_hash": hashlib.sha256(
                        verification_token.encode("utf-8")
                    ).hexdigest(),
                    "email_verification_expires_at": now + timedelta(hours=24),
                }
            },
        )
        try:
            await send_verification_email(user["email"], verification_token)
        except (OSError, smtplib.SMTPException) as error:
            logger.error("Verification email resend failed: %s", type(error).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не вдалося надіслати лист підтвердження.",
            ) from error

    return MessageResponse(
        message="Якщо адреса очікує підтвердження, ми надіслали нове посилання."
    )


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> MessageResponse:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    result = await database.users.update_one(
        {
            "email_verification_token_hash": token_hash,
            "email_verification_expires_at": {"$gt": now},
            "email_verified": False,
        },
        {
            "$set": {"email_verified": True},
            "$unset": {
                "email_verification_token_hash": "",
                "email_verification_expires_at": "",
            },
        },
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Посилання недійсне або прострочене. Запросіть нове.",
        )
    return MessageResponse(message="Електронну пошту підтверджено. Тепер можна увійти.")


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

    if not user.get("email_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Підтвердіть електронну пошту за посиланням у листі.",
        )

    token = create_access_token(str(user["_id"]), user["role"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[UserInDatabase, Depends(get_current_user)],
) -> UserResponse:
    user_data = current_user.model_dump(by_alias=True)
    if current_user.role.value in {"admin", "moderator"}:
        user_data["email_verified"] = True
        user_data["is_approved"] = True
    return UserResponse.model_validate(user_data)
