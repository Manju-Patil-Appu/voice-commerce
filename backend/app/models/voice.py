from sqlalchemy import Column, Integer, ForeignKey, DateTime, Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from app.db.session import Base

class VoiceEmbedding(Base):
    __tablename__ = "voice_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    embedding = Column(ARRAY(Float), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
