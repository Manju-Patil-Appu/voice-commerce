import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import EmailRequest, MessageResponse, ResetPasswordRequest, Token, VerifyEmailRequest
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.services.auth_service import (
    mask_email,
    register_user,
    resend_verification_otp,
    reset_password,
    start_password_reset,
    verify_user_email,
)
from app.services.rate_limit_service import check_rate_limit, rate_limit_key

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        rate_limit_key(request, "register", str(payload.email)),
        settings.AUTH_REGISTER_RATE_LIMIT,
    )
    return register_user(db, payload)


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        rate_limit_key(request, "verify-email", str(payload.email)),
        settings.AUTH_VERIFY_OTP_RATE_LIMIT,
    )
    verify_user_email(db, payload.email, payload.otp)
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(payload: EmailRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        rate_limit_key(request, "resend-otp", str(payload.email)),
        settings.AUTH_RESEND_OTP_RATE_LIMIT,
    )
    resend_verification_otp(db, payload.email)
    return MessageResponse(message="If the account exists and is unverified, a new OTP has been sent")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: EmailRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        rate_limit_key(request, "forgot-password", str(payload.email)),
        settings.AUTH_FORGOT_PASSWORD_RATE_LIMIT,
    )
    start_password_reset(db, payload.email)
    return MessageResponse(message="If the account exists, a password reset OTP has been sent")


@router.post("/reset-password", response_model=MessageResponse)
def complete_password_reset(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        rate_limit_key(request, "reset-password", str(payload.email)),
        settings.AUTH_RESET_PASSWORD_RATE_LIMIT,
    )
    reset_password(db, payload.email, payload.otp, payload.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    check_rate_limit(
        rate_limit_key(request, "login", email),
        settings.AUTH_LOGIN_RATE_LIMIT,
    )

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        logger.info("Login failed: invalid credentials", extra={"email": mask_email(email)})
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        logger.info("Login rejected: email is not verified", extra={"user_id": user.id})
        raise HTTPException(status_code=403, detail="Email is not verified")

    token = create_access_token(subject=str(user.id))
    logger.info("Login succeeded", extra={"user_id": user.id})
    return Token(access_token=token, user_id=user.id)
