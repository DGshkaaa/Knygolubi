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


def is_registered(user: dict | None) -> bool:
    # Older student records may exist before email confirmation. They must not
    # reserve an address. Staff and accounts predating verification stay intact.
    return user is not None and (
        user.get("email_verified", True) or user.get("role") != "student"
    )


async def send_registration_link(database, details: dict) -> dict:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    pending = {
        "name": details["name"],
        "email": details["email"],
        "password_hash": details["password_hash"],
        "email_verification_token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "email_verification_expires_at": now + timedelta(hours=24),
        "created_at": now,
    }
    # This collection is temporary and is never exposed as a user account.
    await database.pending_registrations.insert_one(pending)
    try:
        await send_verification_email(pending["email"], token)
    except (OSError, smtplib.SMTPException) as error:
        logger.error("Registration email delivery failed: %s", type(error).__name__)
        detail = getattr(error, "public_message", None) or (
            "Не вдалося надіслати лист підтвердження. Акаунт не створено. "
            "Спробуйте повторити надсилання або зареєструватися ще раз."
        )
        raise HTTPException(status_code=502, detail=detail) from error
    return pending


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> MessageResponse:
    if not email_is_configured():
        raise HTTPException(status_code=503, detail="Надсилання листів не налаштовано. Зверніться до адміністратора.")
    address = payload.email.lower()
    existing_user = await database.users.find_one({"email": address})
    if is_registered(existing_user):
        raise HTTPException(status_code=409, detail="Ця електронна пошта вже зареєстрована")
    await send_registration_link(database, {
        "name": payload.name,
        "email": address,
        "password_hash": hash_password(payload.password),
    })
    return MessageResponse(message="Перевірте пошту. Акаунт буде створено лише після підтвердження адреси.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    payload: EmailVerificationRequest,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> MessageResponse:
    if not email_is_configured():
        raise HTTPException(status_code=503, detail="Надсилання листів не налаштовано. Зверніться до адміністратора.")
    address = payload.email.lower()
    user = await database.users.find_one({"email": address})
    if not is_registered(user):
        pending = await database.pending_registrations.find_one(
            {"email": address, "email_verification_expires_at": {"$gt": datetime.now(timezone.utc)}},
            sort=[("created_at", -1)],
        )
        # Compatibility with unconfirmed accounts created by earlier versions.
        details = pending or user
        if details is not None:
            await send_registration_link(database, details)
            if pending:
                # Keep the previous link valid when sending fails. Only retire
                # the old attempt once the provider accepted its replacement.
                await database.pending_registrations.delete_one({"_id": pending["_id"]})
    return MessageResponse(message="Якщо адреса очікує підтвердження, ми надіслали нове посилання. Якщо заявка вже прострочена, зареєструйтеся ще раз.")


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> MessageResponse:
    query = {
        "email_verification_token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "email_verification_expires_at": {"$gt": datetime.now(timezone.utc)},
    }
    pending = await database.pending_registrations.find_one(query)
    if pending is None:
        # Previously sent links still work after deploying the new flow.
        result = await database.users.update_one(
            {**query, "email_verified": False, "role": "student"},
            {"$set": {"email_verified": True}, "$unset": {
                "email_verification_token_hash": "", "email_verification_expires_at": "",
            }},
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Посилання недійсне або прострочене. Запросіть нове.")
        return MessageResponse(message="Електронну пошту підтверджено. Тепер можна увійти.")

    existing = await database.users.find_one({"email": pending["email"]})
    if is_registered(existing):
        raise HTTPException(status_code=409, detail="Цю адресу вже підтверджено. Увійдіть до свого акаунта.")
    verified_fields = {
        "name": pending["name"],
        "email": pending["email"],
        "password_hash": pending["password_hash"],
        "email_verified": True,
    }
    if existing is not None:
        # Complete an old unconfirmed student record without losing its ID/data.
        result = await database.users.update_one(
            {"_id": existing["_id"], "email_verified": False, "role": "student"},
            {"$set": verified_fields, "$unset": {
                "email_verification_token_hash": "", "email_verification_expires_at": "",
            }},
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=409, detail="Цю адресу вже підтверджено. Увійдіть до свого акаунта.")
    else:
        user_document = {
            **verified_fields,
            "role": "student", "is_approved": False,
            "notifications": [], "read_books": [], "abandoned_books": [],
            "unfinished_books": [], "returned_books": [], "favorites": [], "wishlist_books": [],
            "joined_at": datetime.now(timezone.utc),
        }
        try:
            await database.users.insert_one(user_document)
        except DuplicateKeyError as error:
            # The unique email index makes concurrent confirmations safe.
            raise HTTPException(status_code=409, detail="Цю адресу вже підтверджено. Увійдіть до свого акаунта.") from error
    await database.pending_registrations.delete_many({"email": pending["email"]})
    return MessageResponse(message="Пошту підтверджено й акаунт створено. Тепер можна увійти.")


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    database: AsyncIOMotorDatabase = Depends(database_dependency),
) -> TokenResponse:
    user = await database.users.find_one({"email": payload.email.lower()})
    if user is None:
        pending = await database.pending_registrations.find_one(
            {"email": payload.email.lower(), "email_verification_expires_at": {"$gt": datetime.now(timezone.utc)}},
            sort=[("created_at", -1)],
        )
        if pending and verify_password(payload.password, pending["password_hash"]):
            raise HTTPException(status_code=403, detail="Підтвердіть пошту, щоб завершити створення акаунта.")
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
