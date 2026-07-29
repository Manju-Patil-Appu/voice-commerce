from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_otp = Column(String, nullable=True)
    verification_expiry = Column(DateTime(timezone=True), nullable=True)
    password_reset_otp = Column(String, nullable=True)
    password_reset_expiry = Column(DateTime(timezone=True), nullable=True)
