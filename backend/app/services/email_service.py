"""Email service — logs to console in development. Replace with real SMTP later."""

from app.config import FRONTEND_URL


def send_verification_email(email: str, token: str) -> None:
    """In development, prints the verification link to the console."""
    url = f"{FRONTEND_URL}/verify-email?token={token}"
    print(f"\n[EMAIL] Verification email for {email}")
    print(f"[EMAIL] Link: {url}\n")


def send_password_reset_email(email: str, token: str) -> None:
    """In development, prints the reset link to the console."""
    url = f"{FRONTEND_URL}/reset-password?token={token}"
    print(f"\n[EMAIL] Password reset email for {email}")
    print(f"[EMAIL] Link: {url}\n")


def send_notification_email(email: str, subject: str, message: str) -> None:
    """In development, logs notification email alert to console."""
    print(f"\n[EMAIL ALERT] To: {email}")
    print(f"[EMAIL ALERT] Subject: {subject}")
    print(f"[EMAIL ALERT] Body: {message}\n")
