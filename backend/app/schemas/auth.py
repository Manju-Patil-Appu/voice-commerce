from pydantic import BaseModel, EmailStr, constr, field_validator

from app.schemas.user import PASSWORD_PATTERN


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: constr(pattern=r"^\d{6}$")


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: constr(pattern=r"^\d{6}$")
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not PASSWORD_PATTERN.fullmatch(value):
            raise ValueError(
                "Password must be 8-64 characters and include uppercase, lowercase, number, and special character"
            )
        return value


class MessageResponse(BaseModel):
    message: str
