from sqlalchemy import text

from app.db.session import Base, engine
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_otp VARCHAR"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_expiry TIMESTAMPTZ"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_otp VARCHAR"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expiry TIMESTAMPTZ"))
print(f"Tables created successfully: {', '.join(sorted(Base.metadata.tables))}")
