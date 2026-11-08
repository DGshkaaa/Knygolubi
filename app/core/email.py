import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def email_is_configured() -> bool:
    return all(
        (
            settings.smtp_host,
            settings.smtp_username,
            settings.smtp_password,
            settings.smtp_from_email,
        )
    )


def _send_email(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, context=context, timeout=15
        ) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)


async def send_verification_email(email: str, token: str) -> None:
    if not email_is_configured():
        raise RuntimeError("SMTP email delivery is not configured")

    verification_url = (
        f"{settings.frontend_url.rstrip('/')}/verify-email?token={token}"
    )
    message = EmailMessage()
    message["Subject"] = "Підтвердіть електронну пошту — Книголюби"
    message["From"] = settings.smtp_from_email or settings.smtp_username
    message["To"] = email
    message.set_content(
        "Щоб підтвердити електронну пошту для облікового запису Книголюби, "
        f"перейдіть за посиланням:\n\n{verification_url}\n\n"
        "Посилання дійсне 24 години."
    )
    await asyncio.to_thread(_send_email, message)
