"""
Email utility for sending notifications via Resend.

In local development (when RESEND_API_KEY is not configured),
this module runs in MOCK mode and logs emails instead of sending.

SETUP GUIDE FOR RESEND:
1. Create a Resend account: https://resend.com/
2. Get your API key from https://resend.com/api-keys
3. Verify your sending domain
4. Add these to your .env file:
   RESEND_API_KEY=re_xxxxxxxxxxxxx
   EMAIL_FROM=your-name@yourdomain.com

5. The resend package is already in dependencies.
"""

import html
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _validate_email_config() -> None:
    """Validate email configuration on module load.

    Raises:
        RuntimeError: If non-mock mode is enabled but RESEND_API_KEY is missing.
    """
    if not settings.EMAIL_MOCK_MODE and not settings.RESEND_API_KEY:
        raise RuntimeError(
            "RESEND_API_KEY is required when EMAIL_MOCK_MODE=False. "
            "Either set RESEND_API_KEY or enable EMAIL_MOCK_MODE for development."
        )


_validate_email_config()

# Mock mode is now explicitly configured
_MOCK_MODE = settings.EMAIL_MOCK_MODE

# Initialize resend client only if not in mock mode
_resend_client = None

if not _MOCK_MODE:
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is required in non-mock mode")
    import resend

    resend.api_key = settings.RESEND_API_KEY
    _resend_client = resend


def sanitize_for_email(content: str) -> str:
    """Escape HTML entities in user-provided content to prevent injection.

    Args:
        content: User-provided text content

    Returns:
        HTML-escaped string safe for use in email bodies
    """
    return html.escape(content)


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
) -> dict | None:
    """Send an email via Resend.

    Args:
        to: Recipient email address or list of addresses
        subject: Email subject line
        html: Email body as HTML

    Returns:
        The Resend API response dict, or None if in mock mode.

    Mock mode (local dev):
        Logs the email details instead of sending.
        Use this for development without a Resend account.
    """
    if _MOCK_MODE:
        logger.info("Email sent in mock mode (not actually sent)")
        return None

    recipients = to if isinstance(to, list) else [to]

    params = {
        "from": settings.EMAIL_FROM,
        "to": recipients,
        "subject": subject,
        "html": html,
    }

    try:
        response = _resend_client.Emails.send(params)
        logger.info(f"Email sent to {len(recipients)} recipient(s)")
        return response
    except Exception as e:
        logger.error(f"Failed to send email to {len(recipients)} recipient(s): {e}")
        raise


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
