import logging
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": "Voice Commerce <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "text": body,
        },
        timeout=15,
    )

    if response.status_code >= 300:
        raise RuntimeError(
            f"Resend API error ({response.status_code}): {response.text}"
        )

    logger.info("Email sent successfully")


def send_verification_email(to_email: str, otp: str) -> None:
    send_email(
        to_email,
        "Verify your StrideSphere email",
        (
            "Welcome to StrideSphere.\n\n"
            f"Your email verification OTP is {otp}.\n"
            f"It expires in {settings.EMAIL_VERIFICATION_OTP_MINUTES} minutes.\n\n"
            "If you did not request this account, you can ignore this email."
        ),
    )


def send_password_reset_email(to_email: str, otp: str) -> None:
    send_email(
        to_email,
        "Reset your StrideSphere password",
        (
            "We received a request to reset your password.\n\n"
            f"Your password reset OTP is {otp}.\n"
            f"It expires in {settings.EMAIL_VERIFICATION_OTP_MINUTES} minutes.\n\n"
            "If you did not request a password reset, you can ignore this email."
        ),
    )