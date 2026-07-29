from datetime import datetime, timedelta
import logging
import secrets

import dns.resolver
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.email_service import send_password_reset_email, send_verification_email


logger = logging.getLogger(__name__)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


def validate_email_domain_has_mx(email: str) -> None:
    domain = email.rsplit("@", 1)[1].rstrip(".")
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.resolver.Timeout,
    ):
        logger.info("Registration rejected: email domain has no MX", extra={"email_domain": domain})
        raise HTTPException(status_code=400, detail="Email domain cannot receive email")

    if not any(str(answer.exchange).rstrip(".") for answer in answers):
        raise HTTPException(status_code=400, detail="Email domain cannot receive email")


def generate_verification_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def otp_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=settings.EMAIL_VERIFICATION_OTP_MINUTES)


def register_user(db: Session, payload: UserCreate) -> User:
    email = str(payload.email).lower()
    validate_email_domain_has_mx(email)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        logger.info("Registration rejected: email already exists", extra={"email": mask_email(email)})
        raise HTTPException(status_code=400, detail="Email already registered")

    otp = generate_verification_otp()
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        is_verified=False,
        verification_otp=otp,
        verification_expiry=otp_expiry(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        send_verification_email(user.email, otp)
    except Exception as exc:
        db.delete(user)
        db.commit()
        logger.exception("Registration failed: verification email was not sent", extra={"email": mask_email(email)})
        raise HTTPException(status_code=502, detail="Could not send verification email") from exc

    logger.info("Registration created pending user", extra={"user_id": user.id})
    return user


def resend_verification_otp(db: Session, email: str) -> User | None:
    user = db.query(User).filter(User.email == str(email).lower()).first()
    if not user:
        logger.info("Verification OTP resend requested for unknown email", extra={"email": mask_email(str(email).lower())})
        return None
    if user.is_verified:
        logger.info("Verification OTP resend rejected: user already verified", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Unable to resend verification OTP")

    otp = generate_verification_otp()
    user.verification_otp = otp
    user.verification_expiry = otp_expiry()
    db.commit()
    db.refresh(user)

    try:
        send_verification_email(user.email, otp)
    except Exception as exc:
        user.verification_otp = None
        user.verification_expiry = None
        db.commit()
        logger.exception("Verification OTP resend failed: email was not sent", extra={"user_id": user.id})
        raise HTTPException(status_code=502, detail="Could not send verification email") from exc

    logger.info("Verification OTP resent", extra={"user_id": user.id})
    return user


def verify_user_email(db: Session, email: str, otp: str) -> User:
    user = db.query(User).filter(User.email == str(email).lower()).first()
    if not user:
        logger.info("Email verification failed: unknown email", extra={"email": mask_email(str(email).lower())})
        raise HTTPException(status_code=400, detail="Invalid or expired verification OTP")
    if user.is_verified:
        logger.info("Email verification failed: user already verified", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired verification OTP")
    if not user.verification_otp or not user.verification_expiry:
        logger.info("Email verification failed: no pending OTP", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired verification OTP")
    if datetime.utcnow() > user.verification_expiry.replace(tzinfo=None):
        user.verification_otp = None
        user.verification_expiry = None
        db.commit()
        logger.info("Email verification failed: OTP expired", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired verification OTP")
    if not secrets.compare_digest(user.verification_otp, otp):
        logger.info("Email verification failed: invalid OTP", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired verification OTP")

    user.is_verified = True
    user.verification_otp = None
    user.verification_expiry = None
    db.commit()
    db.refresh(user)
    logger.info("Email verified successfully", extra={"user_id": user.id})
    return user


def start_password_reset(db: Session, email: str) -> User | None:
    normalized_email = str(email).lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        logger.info("Password reset requested for unknown email", extra={"email": mask_email(normalized_email)})
        return None

    otp = generate_verification_otp()
    user.password_reset_otp = otp
    user.password_reset_expiry = otp_expiry()
    db.commit()
    db.refresh(user)

    try:
        send_password_reset_email(user.email, otp)
    except Exception as exc:
        user.password_reset_otp = None
        user.password_reset_expiry = None
        db.commit()
        logger.exception("Password reset OTP email was not sent", extra={"user_id": user.id})
        return None

    logger.info("Password reset OTP sent", extra={"user_id": user.id})
    return user


def reset_password(db: Session, email: str, otp: str, new_password: str) -> User:
    user = db.query(User).filter(User.email == str(email).lower()).first()
    if not user:
        logger.info("Password reset failed: unknown email", extra={"email": mask_email(str(email).lower())})
        raise HTTPException(status_code=400, detail="Invalid or expired password reset OTP")
    if not user.password_reset_otp or not user.password_reset_expiry:
        logger.info("Password reset failed: no pending OTP", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired password reset OTP")
    if datetime.utcnow() > user.password_reset_expiry.replace(tzinfo=None):
        user.password_reset_otp = None
        user.password_reset_expiry = None
        db.commit()
        logger.info("Password reset failed: OTP expired", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired password reset OTP")
    if not secrets.compare_digest(user.password_reset_otp, otp):
        logger.info("Password reset failed: invalid OTP", extra={"user_id": user.id})
        raise HTTPException(status_code=400, detail="Invalid or expired password reset OTP")

    user.password_hash = hash_password(new_password)
    user.password_reset_otp = None
    user.password_reset_expiry = None
    db.commit()
    db.refresh(user)
    logger.info("Password reset completed", extra={"user_id": user.id})
    return user
