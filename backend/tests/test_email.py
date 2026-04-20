"""Tests for the email utility (Gmail SMTP backend).

These tests mock the SMTP server to avoid sending real emails.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.utils.email import (
    _send_smtp,
    is_mock_mode,
    sanitize_for_email,
    send_email,
    send_verification_email,
)


class TestSanitizeForEmail:
    """HTML sanitization tests — no mocking needed."""

    def test_escapes_html_tags(self):
        assert sanitize_for_email("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_escapes_ampersands(self):
        assert sanitize_for_email("a & b") == "a &amp; b"

    def test_plain_text_unchanged(self):
        assert sanitize_for_email("Hello world") == "Hello world"


class TestMockMode:
    """Verify mock mode behavior — send_email returns None when in mock mode.

    conftest.py forces EMAIL_MOCK_MODE=true for all tests, so no patching needed here.
    """

    @pytest.mark.asyncio
    async def test_send_email_returns_none_in_mock_mode(self):
        result = await send_email(
            to="test@example.com", subject="Test", html="<p>Hello</p>"
        )
        assert result is None

    def test_is_mock_mode_reflects_settings(self):
        assert is_mock_mode() is True

    @pytest.mark.asyncio
    async def test_send_verification_email_returns_none_in_mock_mode(self):
        result = await send_verification_email(
            to="test@example.com",
            full_name="Test User",
            verification_link="http://localhost/verify?token=abc",
        )
        assert result is None


@patch("app.utils.email._send_smtp")
class TestSmtpSending:
    """Test the actual SMTP path by mocking the sync send function.

    These tests patch settings to disable mock mode and exercise the SMTP code path.
    """

    @pytest.mark.asyncio
    async def test_send_email_calls_smtp(self, mock_send):
        """send_email should call _send_smtp with correct arguments."""
        with patch("app.utils.email.settings") as mock_settings:
            mock_settings.EMAIL_MOCK_MODE = False
            await send_email(
                to="recipient@example.com",
                subject="Test Subject",
                html="<p>Hello</p>",
            )
        mock_send.assert_called_once_with(
            ["recipient@example.com"],
            "Test Subject",
            "<p>Hello</p>",
        )

    @pytest.mark.asyncio
    async def test_send_email_handles_list_of_recipients(self, mock_send):
        """send_email should accept a list of recipients."""
        with patch("app.utils.email.settings") as mock_settings:
            mock_settings.EMAIL_MOCK_MODE = False
            await send_email(
                to=["a@example.com", "b@example.com"],
                subject="Multi",
                html="<p>Hi</p>",
            )
        mock_send.assert_called_once_with(
            ["a@example.com", "b@example.com"],
            "Multi",
            "<p>Hi</p>",
        )

    @pytest.mark.asyncio
    async def test_send_email_raises_on_smtp_failure(self, mock_send):
        """send_email should re-raise SMTP errors."""
        mock_send.side_effect = Exception("SMTP connection failed")
        with patch("app.utils.email.settings") as mock_settings:
            mock_settings.EMAIL_MOCK_MODE = False
            with pytest.raises(Exception, match="SMTP connection failed"):
                await send_email(
                    to="test@example.com",
                    subject="Fail",
                    html="<p>Nope</p>",
                )


class TestSendSmtp:
    """Test the synchronous _send_smtp function with a mocked SMTP server."""

    @patch("app.utils.email.smtplib.SMTP")
    def test_smtp_flow(self, mock_smtp_cls):
        """_send_smtp should connect, start TLS, login, and send."""
        mock_server = MagicMock()
        mock_server.sendmail.return_value = {}  # Empty dict = all recipients accepted
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.utils.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USE_TLS = True
            mock_settings.SMTP_REQUIRE_AUTH = True
            mock_settings.GMAIL_USER = "test@gmail.com"
            mock_settings.GMAIL_APP_PASSWORD = "testpass"
            _send_smtp(["to@example.com"], "Subject", "<p>Body</p>")

        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
        sent_message = mock_server.sendmail.call_args[0][2]
        assert "Subject: Subject" in sent_message
        assert "to@example.com" in sent_message
        assert "text/html" in sent_message

    @patch("app.utils.email.smtplib.SMTP")
    def test_smtp_raises_on_refused_recipients(self, mock_smtp_cls):
        """_send_smtp should raise SMTPRecipientsRefused when recipients are rejected."""
        mock_server = MagicMock()
        mock_server.sendmail.return_value = {"refused@example.com": (550, b"Rejected")}
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(Exception):
            _send_smtp(["refused@example.com"], "Subject", "<p>Body</p>")
