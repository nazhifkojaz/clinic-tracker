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

# Mock mode flag
_MOCK_MODE = not bool(settings.RESEND_API_KEY)

# Initialize resend client only if API key is configured
_resend_client = None

if not _MOCK_MODE:
    import resend

    resend.api_key = settings.RESEND_API_KEY
    _resend_client = resend


def _is_configured() -> bool:
    """Check if Resend is properly configured."""
    return bool(settings.RESEND_API_KEY)


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
    if not _is_configured():
        logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}")
        logger.debug(f"[MOCK EMAIL] Body: {html[:500]}...")
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
        logger.info(f"Email sent to {recipients}: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to send email to {recipients}: {e}")
        raise


def is_mock_mode() -> bool:
    """Check if email is running in mock mode."""
    return _MOCK_MODE
