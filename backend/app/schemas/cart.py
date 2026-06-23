from pydantic import BaseModel

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int

    class Config:
        from_attributes = True
