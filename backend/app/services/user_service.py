from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


def ensure_user_exists(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        return user

    # Auto-provision local demo user for direct UI testing flows.
    user = User(
        id=user_id,
        email=f"demo_user_{user_id}@local.test",
        password_hash="demo_password_hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Keep postgres sequence aligned with explicit id insert.
    db.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('users','id'), "
            "GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1));"
        )
    )
    db.commit()
    return user
