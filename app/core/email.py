import asyncio
import smtplib
import ssl
from html import escape
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
            refused = server.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(settings.smtp_username, settings.smtp_password)
            refused = server.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)


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
    message.add_alternative(
        '<html lang="uk"><body style="margin:0;padding:32px 16px;background:#f7f7f5;color:#23262a;font-family:Arial,sans-serif">'
        '<div style="max-width:520px;margin:auto;padding:32px;background:#ffffff;border-radius:16px">'
        '<p style="color:#b84e21;letter-spacing:2px;font-size:12px">КНИГОЛЮБИ</p>'
        '<h1 style="font-size:28px">Ваша наступна історія вже поруч</h1>'
        '<p style="line-height:1.7">Підтвердіть електронну пошту, щоб увійти до свого читацького профілю.</p>'
        f'<p style="margin:28px 0"><a href="{escape(verification_url, quote=True)}" '
        'style="display:inline-block;padding:15px 22px;background:#d85b26;color:white;border-radius:10px;text-decoration:none">Підтвердити пошту</a></p>'
        '<p style="line-height:1.7">Посилання дійсне 24 години. Після підтвердження модератор схвалить доступ до обміну книгами.</p>'
        '<p style="font-size:13px;color:#62676c">Якщо ви не створювали профіль, просто проігноруйте цей лист.</p>'
        f'<p style="word-break:break-all;font-size:12px">{escape(verification_url)}</p>'
        '</div></body></html>',
        subtype="html",
    )
    await asyncio.to_thread(_send_email, message)
