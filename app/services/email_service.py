import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage as SMTPEmailMessage

import aiosmtplib
from sqlalchemy import asc, select

from app.core.config import settings
from app.db.models.email_outbox import EmailOutbox
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("tcg_trove.email")
MAX_EMAIL_RETRIES = 5


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


async def _deliver_email_now_async(message: EmailMessage) -> None:
    """
    Asynchronously delivers an email using aiosmtplib.
    Fails early if SMTP is disabled.
    """
    if not settings.smtp_enabled:
        logger.info(
            "Email delivery disabled; message queued only in logs",
            extra={"to": message.to, "subject": message.subject},
        )
        return

    smtp_message = SMTPEmailMessage()
    smtp_message["From"] = settings.smtp_from_email
    smtp_message["To"] = message.to
    smtp_message["Subject"] = message.subject
    smtp_message.set_content(message.body)

    try:
        await aiosmtplib.send(
            smtp_message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            use_tls=settings.smtp_use_tls,
            username=settings.smtp_username,
            password=settings.smtp_password,
            timeout=10,
        )
    except Exception:
        logger.exception(
            "Async email delivery failed",
            extra={"to": message.to, "subject": message.subject},
        )
        raise


async def enqueue_email_async(message: EmailMessage) -> int:
    """
    Persists an email message to the outbox table for background processing.
    """
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC).replace(tzinfo=None)
        item = EmailOutbox(
            recipient=message.to,
            subject=message.subject,
            body=message.body,
            status="pending",
            retry_count=0,
            next_attempt_at=now,
            created_at=now,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return int(item.id)


async def async_process_outbox(batch_size: int = 20) -> None:
    """
    Asynchronously processes pending emails from the outbox.
    Implements exponential backoff for retries.
    """
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC).replace(tzinfo=None)
        
        # Select pending or retry items that are due
        result = await db.execute(
            select(EmailOutbox)
            .where(
                EmailOutbox.status.in_(["pending", "retry"]),
                EmailOutbox.next_attempt_at <= now,
            )
            .order_by(asc(EmailOutbox.next_attempt_at))
            .limit(batch_size)
        )
        pending = result.scalars().all()

        for item in pending:
            msg = EmailMessage(
                to=str(item.recipient),
                subject=str(item.subject),
                body=str(item.body),
            )
            try:
                await _deliver_email_now_async(msg)
                item.status = "sent"
                item.sent_at = datetime.now(UTC).replace(tzinfo=None)
                item.last_error = None
            except Exception as exc:
                item.retry_count = int(item.retry_count or 0) + 1
                if item.retry_count >= MAX_EMAIL_RETRIES:
                    item.status = "failed"
                else:
                    item.status = "retry"
                    # Exponential backoff: 1m, 2m, 4m, 8m... capped at 1h
                    backoff_seconds = min(60 * (2 ** max(item.retry_count - 1, 0)), 3600)
                    item.next_attempt_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                        seconds=backoff_seconds
                    )
                item.last_error = str(exc)[:1000]

        await db.commit()


async def send_email_async(message: EmailMessage) -> None:
    """
    Primary entry point for sending emails. Enqueues the message and 
    optionally triggers an immediate batch process if background worker is disabled.
    """
    await enqueue_email_async(message)
    if not settings.email_outbox_worker_enabled:
        await async_process_outbox(batch_size=10)


async def send_confirmation_email_async(to: str, event_name: str, details: str) -> None:
    """
    High-level helper for sending confirmation emails.
    """
    await send_email_async(
        EmailMessage(
            to=to,
            subject=f"TCG Trove confirmation: {event_name}",
            body=details,
        )
    )


# --- Sync Wrappers for compatibility ---

def enqueue_email(message: EmailMessage) -> int:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(enqueue_email_async(message))
    
    if loop.is_running():
        # This is a hack for sync code called from async context (like FastAPI def routers)
        # In a real "Final Boss" scenario, we'd make the caller async.
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(enqueue_email_async(message))
    return asyncio.run(enqueue_email_async(message))


def process_outbox(batch_size: int = 20) -> None:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
    except RuntimeError:
        pass
    asyncio.run(async_process_outbox(batch_size))


def send_email(message: EmailMessage) -> None:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
    except RuntimeError:
        pass
    asyncio.run(send_email_async(message))


def send_confirmation_email(to: str, event_name: str, details: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
    except RuntimeError:
        pass
    asyncio.run(send_confirmation_email_async(to, event_name, details))
