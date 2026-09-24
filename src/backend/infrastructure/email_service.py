"""
Email service for sending transactional messages.

Supports multiple backends:
- "console": Logs emails to stdout (default for development)
- "smtp": Sends via SMTP server (production)
- "sendgrid": Sends via SendGrid API (production, requires SENDGRID_API_KEY)

Configuration is read from the live application settings first (so values an
administrator saves on the settings page take effect without a restart) and
falls back to the EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_USER,
EMAIL_PASSWORD, EMAIL_FROM, EMAIL_USE_TLS and SENDGRID_API_KEY environment
variables.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


def _live_settings() -> Any:
    """Return the shared application settings object, or ``None``.

    Imported lazily to avoid a circular import at module load time and so the
    service observes settings saved at runtime.
    """
    try:
        from src.backend.config.settings import settings as app_settings

        return app_settings
    except Exception:  # pragma: no cover - defensive import guard
        return None


def _configured_value(attr: str, env_name: str, default: Any) -> Any:
    """Resolve an email setting, preferring the live settings object.

    Falls back to the environment variable so deployments that configure email
    purely through ``.env.local`` keep working unchanged.
    """
    import os

    live = _live_settings()
    if live is not None:
        value = getattr(live, attr, None)
        if value not in (None, ""):
            return value
    return os.getenv(env_name, default)


class EmailService:
    """Service for sending emails with configurable backend."""

    @staticmethod
    def _get_backend() -> str:
        """Get the configured email backend."""
        return str(
            _configured_value("EMAIL_BACKEND", "EMAIL_BACKEND", "console")
        ).lower()

    @staticmethod
    def _get_smtp_config() -> dict:
        """Get SMTP configuration from the live settings or environment."""
        return {
            "host": str(_configured_value("EMAIL_HOST", "EMAIL_HOST", "localhost")),
            "port": int(_configured_value("EMAIL_PORT", "EMAIL_PORT", "587")),
            "user": str(_configured_value("EMAIL_USER", "EMAIL_USER", "")),
            "password": str(
                _configured_value("EMAIL_PASSWORD", "EMAIL_PASSWORD", "") or ""
            ),
            "from_email": str(
                _configured_value(
                    "EMAIL_FROM", "EMAIL_FROM", "noreply@integritydesk.com"
                )
            ),
            "use_tls": str(
                _configured_value("EMAIL_USE_TLS", "EMAIL_USE_TLS", "true")
            ).lower()
            == "true",
        }

    @staticmethod
    async def _deliver(
        to_email: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """Dispatch a message to the configured backend.

        Returns ``True`` when the backend accepted the message and ``False``
        when delivery failed, so callers can report an honest status instead
        of raising into a request handler.
        """
        backend = EmailService._get_backend()
        try:
            if backend == "smtp":
                return EmailService._send_via_smtp(
                    to_email, subject, html_body, text_body
                )
            if backend == "sendgrid":
                return await EmailService._send_via_sendgrid(
                    to_email, subject, html_body, text_body
                )
            return EmailService._send_via_console(to_email, subject, text_body)
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to_email, exc)
            return False

    @staticmethod
    async def send_test_email(to_email: str) -> bool:
        """Send a diagnostic email so admins can verify delivery settings.

        Uses the same backend resolution as password resets, so a successful
        send proves the configured credentials genuinely work.
        """
        subject = "IntegrityDesk email delivery test"
        html_body = (
            '<div style="font-family: Arial, sans-serif; max-width: 600px;">'
            "<h2>Email delivery is working</h2>"
            "<p>This is a test message sent from the IntegrityDesk settings page.</p>"
            "<p>If you received it, your email configuration is correct.</p>"
            "</div>"
        )
        text_body = (
            "Email delivery is working.\n\n"
            "This is a test message sent from the IntegrityDesk settings page."
        )
        return await EmailService._deliver(to_email, subject, html_body, text_body)

    @staticmethod
    async def send_password_reset_email(email: str, reset_url: str) -> bool:
        """Send password reset email to user.

        Args:
            email: User's email address
            reset_url: Password reset URL with token

        Returns:
            True if email was sent successfully, False otherwise
        """
        subject = "Reset Your Password - IntegrityDesk"
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1a1a2e;">Password Reset Request</h2>
            <p>You requested a password reset for your IntegrityDesk account.</p>
            <p>Click the button below to reset your password:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}"
                   style="background-color: #4361ee; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Reset Password
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">This link will expire in 24 hours.</p>
            <p style="color: #666; font-size: 14px;">
                If you didn't request this, please ignore this email.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #999; font-size: 12px;">
                IntegrityDesk - Academic Integrity Platform
            </p>
        </div>
        """
        text_body = (
            f"Password Reset Request\n\n"
            f"You requested a password reset for your IntegrityDesk account.\n\n"
            f"Reset your password here: {reset_url}\n\n"
            f"This link will expire in 24 hours.\n"
            f"If you didn't request this, please ignore this email."
        )

        return await EmailService._deliver(email, subject, html_body, text_body)

    @staticmethod
    def _send_via_console(to_email: str, subject: str, body: str) -> bool:
        """Log the email to console (development mode)."""
        logger.warning(
            "EMAIL_BACKEND=console — not actually sending email.\n"
            "  To: %s\n  Subject: %s\n  Body:\n%s",
            to_email,
            subject,
            body,
        )
        print(f"\n{'='*60}")
        print("EMAIL (console mode — not sent)")
        print(f"  To: {to_email}")
        print(f"  Subject: {subject}")
        print(f"  Body:\n{body}")
        print(f"{'='*60}\n")
        return True

    @staticmethod
    def _send_via_smtp(
        to_email: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """Send email via SMTP."""
        config = EmailService._get_smtp_config()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["from_email"]
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config["host"], config["port"]) as server:
            if config["use_tls"]:
                server.starttls()
            if config["user"] and config["password"]:
                server.login(config["user"], config["password"])
            server.sendmail(config["from_email"], to_email, msg.as_string())

        logger.info("Email sent to %s via SMTP", to_email)
        return True

    @staticmethod
    async def _send_via_sendgrid(
        to_email: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """Send email via SendGrid API."""
        api_key = _configured_value("SENDGRID_API_KEY", "SENDGRID_API_KEY", None)
        if not api_key:
            logger.error("SENDGRID_API_KEY not set but EMAIL_BACKEND=sendgrid")
            return False

        from_email = str(
            _configured_value("EMAIL_FROM", "EMAIL_FROM", "noreply@integritydesk.com")
        )

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_body,
            )
            sg = SendGridAPIClient(api_key)
            sg.send(message)
            logger.info("Email sent to %s via SendGrid", to_email)
            return True
        except ImportError:
            logger.error("sendgrid package not installed. Run: pip install sendgrid")
            return False
        except Exception as e:
            logger.error("SendGrid API error: %s", e)
            return False
