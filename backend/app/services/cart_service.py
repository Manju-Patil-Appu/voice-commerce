from typing import Any
from sqlalchemy.orm import Session
from app.models.cart import CartItem
from app.models.product import Product
from app.services.product_service import find_first_product


def _cart_items_for_user(db: Session, user_id: int):
    return db.query(CartItem).filter(CartItem.user_id == user_id).all()


def handle_cart(intent: str, user_id: int, entities: dict, db: Session) -> dict[str, Any]:
    quantity = int(entities.get("quantity", 1) or 1)

    if intent == "view_cart":
        items = _cart_items_for_user(db, user_id)
        detailed_items = []
        total_amount = 0.0
        for i in items:
            product = db.query(Product).filter(Product.id == i.product_id).first()
            line_price = float(product.price * i.quantity) if product else 0.0
            total_amount += line_price
            detailed_items.append(
                {
                    "id": i.id,
                    "product_id": i.product_id,
                    "name": product.name if product else None,
                    "price": product.price if product else None,
                    "quantity": i.quantity,
                    "line_total": round(line_price, 2),
                }
            )
        return {
            "action": "view_cart",
            "user_id": user_id,
            "items": detailed_items,
            "total_amount": round(total_amount, 2),
        }

    product_id = entities.get("product_id")
    product = None
    if product_id:
        product = db.query(Product).filter(Product.id == int(product_id)).first()
    else:
        product = find_first_product(db, entities)
        # Fallback: if full filter misses, retry by product name only.
        if not product and entities.get("name"):
            product = find_first_product(db, {"name": entities.get("name")})
        # Additional fallback for voice commands:
        # brand + size or category + size is often enough to select a single SKU.
        if not product:
            relaxed = {}
            if entities.get("brand"):
                relaxed["brand"] = entities.get("brand")
            if entities.get("category"):
                relaxed["category"] = entities.get("category")
            if entities.get("size"):
                relaxed["size"] = entities.get("size")
            if relaxed:
                product = find_first_product(db, relaxed)

    if not product:
        return {"action": intent, "error": "product_not_found"}

    if intent == "add_to_cart":
        if product.stock < quantity:
            return {"action": intent, "error": "out_of_stock", "available": product.stock}

        item = (
            db.query(CartItem)
            .filter(CartItem.user_id == user_id, CartItem.product_id == product.id)
            .first()
        )
        if item:
            item.quantity += quantity
        else:
            item = CartItem(user_id=user_id, product_id=product.id, quantity=quantity)
            db.add(item)

        db.commit()
        db.refresh(item)
        return {
            "action": intent,
            "user_id": user_id,
            "item": {"id": item.id, "product_id": item.product_id, "quantity": item.quantity},
        }

    if intent == "remove_from_cart":
        item = (
            db.query(CartItem)
            .filter(CartItem.user_id == user_id, CartItem.product_id == product.id)
            .first()
        )
        if not item:
            return {"action": intent, "error": "item_not_in_cart"}

        db.delete(item)
        db.commit()
        return {"action": intent, "user_id": user_id, "removed_product_id": product.id}

    return {"action": intent, "error": "unsupported_cart_action"}
