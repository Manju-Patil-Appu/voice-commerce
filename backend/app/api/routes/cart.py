from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cart import CartItemCreate
from app.services import cart_service
from app.services.user_service import ensure_user_exists

router = APIRouter()


@router.get("/")
def list_cart(user_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_user_exists(db, user_id)
    return cart_service.handle_cart("view_cart", user_id, {}, db)


@router.post("/")
def add_to_cart(payload: CartItemCreate, user_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_user_exists(db, user_id)
    entities = {"product_id": payload.product_id, "quantity": payload.quantity}
    return cart_service.handle_cart("add_to_cart", user_id, entities, db)


@router.delete("/{product_id}")
def remove_from_cart(product_id: int, user_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_user_exists(db, user_id)
    return cart_service.handle_cart("remove_from_cart", user_id, {"product_id": product_id}, db)
