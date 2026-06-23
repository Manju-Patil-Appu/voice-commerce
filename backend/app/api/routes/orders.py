from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.order import Order
from app.services import order_service
from app.services.user_service import ensure_user_exists

router = APIRouter()


@router.get("/")
def list_orders(user_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_user_exists(db, user_id)
    rows = db.query(Order).filter(Order.user_id == user_id).order_by(Order.id.desc()).all()
    return {
        "user_id": user_id,
        "items": [
            {
                "id": row.id,
                "order_id": row.order_id or row.id,
                "total_amount": row.total_amount,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "pricing": row.pricing,
                "payment": row.payment,
                "delivery": row.delivery,
            }
            for row in rows
        ],
    }


@router.post("/checkout")
def checkout(
    user_id: int,
    payload: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_user_exists(db, user_id)
    return order_service.checkout(
        user_id=user_id,
        db=db,
        customer=payload.get("customer"),
        delivery=payload.get("delivery"),
        payment_method=payload.get("payment_method") or "COD",
        discount=float(payload.get("discount") or 0),
    )
