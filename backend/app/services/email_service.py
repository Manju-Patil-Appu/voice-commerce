import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings


logger = logging.getLogger(__name__)


def _smtp_config() -> dict[str, object]:
    placeholders = {
        "SMTP_USERNAME": "your-gmail-address@gmail.com",
        "SMTP_PASSWORD": "your-google-app-password",
        "SMTP_FROM": "your-gmail-address@gmail.com",
    }
    required = {
        "SMTP_HOST": settings.SMTP_HOST,
        "SMTP_PORT": settings.SMTP_PORT,
        "SMTP_USERNAME": settings.SMTP_USERNAME,
        "SMTP_PASSWORD": settings.SMTP_PASSWORD,
        "SMTP_FROM": settings.SMTP_FROM,
        "SMTP_TLS": settings.SMTP_TLS,
    }
    missing = [name for name, value in required.items() if value is None or value == ""]
    if missing:
        raise RuntimeError(
            "Email delivery is not configured. Missing required SMTP environment variables: "
            + ", ".join(missing)
        )
    placeholder_values = [
        name for name, placeholder in placeholders.items() if required.get(name) == placeholder
    ]
    if placeholder_values:
        raise RuntimeError(
            "Email delivery is not configured. Replace placeholder SMTP environment variables: "
            + ", ".join(placeholder_values)
        )

    return required


def send_email(to_email: str, subject: str, body: str) -> None:
    smtp = _smtp_config()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("VoxCom", str(smtp["SMTP_FROM"])))
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(str(smtp["SMTP_HOST"]), int(smtp["SMTP_PORT"]), timeout=10) as client:
        if bool(smtp["SMTP_TLS"]):
            client.starttls()
        client.login(str(smtp["SMTP_USERNAME"]), str(smtp["SMTP_PASSWORD"]))
        client.send_message(message)

    logger.info("Email sent", extra={"to_domain": to_email.rsplit("@", 1)[-1], "subject": subject})


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
            "We received a request to reset your StrideSphere password.\n\n"
            f"Your password reset OTP is {otp}.\n"
            f"It expires in {settings.EMAIL_VERIFICATION_OTP_MINUTES} minutes.\n\n"
            "If you did not request a password reset, you can ignore this email."
        ),
    )
