from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.session import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    brand = Column(String, index=True, nullable=True)
    size = Column(String, index=True, nullable=True)
    color = Column(String, index=True, nullable=True)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    images = Column(ARRAY(String), nullable=True)
    embedding = Column(ARRAY(Float), nullable=True)
