import logging
import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    resend.Emails.send({
        "from": "Voice Commerce <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "text": body,
    })

    logger.info(f"Email sent to {to_email}")


def send_verification_email(to_email: str, otp: str):
    send_email(
        to_email,
        "Verify your StrideSphere email",
        (
            "Welcome to StrideSphere.\n\n"
            f"Your verification OTP is: {otp}\n\n"
            f"It expires in {settings.EMAIL_VERIFICATION_OTP_MINUTES} minutes."
        ),
    )


def send_password_reset_email(to_email: str, otp: str):
    send_email(
        to_email,
        "Reset your StrideSphere password",
        (
            "Your password reset OTP is:\n\n"
            f"{otp}\n\n"
            f"It expires in {settings.EMAIL_VERIFICATION_OTP_MINUTES} minutes."
        ),
    )