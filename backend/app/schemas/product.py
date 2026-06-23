from pydantic import BaseModel

class ProductOut(BaseModel):
    id: int
    name: str
    category: str | None = None
    brand: str | None = None
    size: str | None = None
    color: str | None = None
    description: str | None = None
    price: float
    stock: int | None = None
    images: list[str] | None = None

    class Config:
        from_attributes = True
