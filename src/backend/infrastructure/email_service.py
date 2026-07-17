"""
Email service for sending password reset emails.

Supports multiple backends:
- "console": Logs emails to stdout (default for development)
- "smtp": Sends via SMTP server (production)
- "sendgrid": Sends via SendGrid API (production, requires SENDGRID_API_KEY)

Configure via EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD,
EMAIL_FROM, and SENDGRID_API_KEY environment variables.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with configurable backend."""

    @staticmethod
    def _get_backend() -> str:
        """Get the configured email backend."""
        import os
        return os.getenv("EMAIL_BACKEND", "console").lower()

    @staticmethod
    def _get_smtp_config() -> dict:
        """Get SMTP configuration from environment."""
        import os
        return {
            "host": os.getenv("EMAIL_HOST", "localhost"),
            "port": int(os.getenv("EMAIL_PORT", "587")),
            "user": os.getenv("EMAIL_USER", ""),
            "password": os.getenv("EMAIL_PASSWORD", ""),
            "from_email": os.getenv("EMAIL_FROM", "noreply@integritydesk.com"),
            "use_tls": os.getenv("EMAIL_USE_TLS", "true").lower() == "true",
        }

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

        backend = EmailService._get_backend()

        try:
            if backend == "smtp":
                return EmailService._send_via_smtp(email, subject, html_body, text_body)
            elif backend == "sendgrid":
                return await EmailService._send_via_sendgrid(email, subject, html_body, text_body)
            else:
                return EmailService._send_via_console(email, subject, reset_url)
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            return False

    @staticmethod
    def _send_via_console(email: str, subject: str, reset_url: str) -> bool:
        """Log email to console (development mode)."""
        logger.warning(
            f"EMAIL_BACKEND=console — not actually sending email.\n"
            f"  To: {email}\n"
            f"  Subject: {subject}\n"
            f"  Reset URL: {reset_url}"
        )
        print(f"\n{'='*60}")
        print(f"PASSWORD RESET EMAIL (console mode — not sent)")
        print(f"  To: {email}")
        print(f"  Subject: {subject}")
        print(f"  Reset URL: {reset_url}")
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

        logger.info(f"Password reset email sent to {to_email} via SMTP")
        return True

    @staticmethod
    async def _send_via_sendgrid(
        to_email: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """Send email via SendGrid API."""
        import os
        api_key = os.getenv("SENDGRID_API_KEY")
        if not api_key:
            logger.error("SENDGRID_API_KEY not set but EMAIL_BACKEND=sendgrid")
            return False

        from_email = os.getenv("EMAIL_FROM", "noreply@integritydesk.com")

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
            logger.info(f"Password reset email sent to {to_email} via SendGrid")
            return True
        except ImportError:
            logger.error("sendgrid package not installed. Run: pip install sendgrid")
            return False
        except Exception as e:
            logger.error(f"SendGrid API error: {e}")
            return False