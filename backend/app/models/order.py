from sqlalchemy import Column, Integer, ForeignKey, Float, String, DateTime, JSON
from sqlalchemy.sql import func

from app.db.session import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    total_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="pending")
    customer = Column(JSON, nullable=True)
    items = Column(JSON, nullable=True)
    pricing = Column(JSON, nullable=True)
    payment = Column(JSON, nullable=True)
    delivery = Column(JSON, nullable=True)
    invoice_text = Column(String, nullable=True)
