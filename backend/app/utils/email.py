"""
Email utility for sending notifications via Gmail SMTP.

In local development (when GMAIL_USER/GMAIL_APP_PASSWORD are not configured),
this module runs in MOCK mode and logs emails instead of sending.

SETUP GUIDE FOR GMAIL SMTP:
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification (required for App Passwords)
3. Go to https://myaccount.google.com/apppasswords
4. Create a new App Password (select "Mail" → "Other", name it "Smart Clinic Tracker")
5. Copy the 16-character password
6. Add these to your .env file:
   GMAIL_USER=yourname@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   EMAIL_MOCK_MODE=False

Free tier: 500 emails/day via Gmail SMTP.
"""

import asyncio
import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)

_SMTP_SERVER = "smtp.gmail.com"
_SMTP_PORT = 587


def _validate_email_config() -> None:
    """Validate email configuration on module load.

    Raises:
        RuntimeError: If non-mock mode is enabled but Gmail credentials are missing.
    """
    if not settings.EMAIL_MOCK_MODE and (
        not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD
    ):
        raise RuntimeError(
            "GMAIL_USER and GMAIL_APP_PASSWORD are required when EMAIL_MOCK_MODE=False. "
            "Either set Gmail credentials or enable EMAIL_MOCK_MODE for development."
        )


_validate_email_config()

# Mock mode is now explicitly configured
_MOCK_MODE = settings.EMAIL_MOCK_MODE

# Resolve EMAIL_FROM: use GMAIL_USER if EMAIL_FROM is still the default
if settings.EMAIL_FROM == "noreply@example.com" and settings.GMAIL_USER:
    _EMAIL_FROM = settings.GMAIL_USER
else:
    _EMAIL_FROM = settings.EMAIL_FROM


def sanitize_for_email(content: str) -> str:
    """Escape HTML entities in user-provided content to prevent injection.

    Args:
        content: User-provided text content

    Returns:
        HTML-escaped string safe for use in email bodies
    """
    return html.escape(content)


def _send_smtp(to: list[str], subject: str, html_body: str) -> None:
    """Synchronous SMTP send — called via asyncio.to_thread."""
    msg = MIMEMultipart("alternative")
    msg["From"] = _EMAIL_FROM
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(_SMTP_SERVER, _SMTP_PORT) as server:
        server.starttls()
        server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
        server.sendmail(_EMAIL_FROM, to, msg.as_string())


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
) -> dict | None:
    """Send an email via Gmail SMTP.

    Args:
        to: Recipient email address or list of addresses
        subject: Email subject line
        html: Email body as HTML

    Returns:
        None (Gmail SMTP doesn't return a tracking ID like Resend).

    Mock mode (local dev):
        Logs the email details instead of sending.
        Use this for development without Gmail credentials.
    """
    if _MOCK_MODE:
        logger.info("Email sent in mock mode (not actually sent)")
        return None

    recipients = to if isinstance(to, list) else [to]

    try:
        await asyncio.to_thread(_send_smtp, recipients, subject, html)
        logger.info(f"Email sent to {len(recipients)} recipient(s)")
    except Exception as e:
        logger.error(f"Failed to send email to {len(recipients)} recipient(s): {e}")
        raise

    return None


def is_mock_mode() -> bool:
    """Check if email is running in mock mode."""
    return _MOCK_MODE


async def send_verification_email(
    to: str, full_name: str, verification_link: str
) -> dict | None:
    """Send an email verification link to a newly registered user."""
    safe_name = sanitize_for_email(full_name)
    safe_link = sanitize_for_email(verification_link)
    subject = "Verify your Smart Clinic Tracker account"
    html_body = f"""
    <p>Hi {safe_name},</p>
    <p>Please verify your email address by clicking the link below:</p>
    <p><a href="{safe_link}">{safe_link}</a></p>
    <p>This link expires in 24 hours.</p>
    <p>If you did not create this account, please ignore this email.</p>
    """
    return await send_email(to=to, subject=subject, html=html_body)
