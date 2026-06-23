from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.cart import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User


TAX_RATE = 0.05
DELIVERY_FEE = 50.0
DEFAULT_DISCOUNT = 0.0


def _money(value: float) -> float:
    return round(float(value), 2)


def _default_customer(user: User | None, customer: dict[str, Any] | None) -> dict[str, str]:
    customer = customer or {}
    email = customer.get("email") or (user.email if user else "")
    name = customer.get("name") or (email.split("@")[0] if email else "Customer")
    return {
        "name": str(name),
        "email": str(email),
        "phone": str(customer.get("phone") or ""),
    }


def _default_delivery(delivery: dict[str, Any] | None) -> dict[str, str]:
    delivery = delivery or {}
    return {
        "address": str(delivery.get("address") or "Demo delivery address"),
        "city": str(delivery.get("city") or "Bengaluru"),
        "pincode": str(delivery.get("pincode") or "560001"),
        "status": str(delivery.get("status") or "Processing"),
    }


def generate_invoice(order: dict[str, Any]) -> str:
    customer = order.get("customer", {})
    delivery = order.get("delivery", {})
    pricing = order.get("pricing", {})
    payment = order.get("payment", {})
    items = order.get("items", [])

    lines = [
        "-----------------------------------------",
        "ORDER INVOICE",
        "-----------------------------------------",
        f"Order ID: {order.get('order_id', '')}",
        f"Date: {order.get('created_at', '')}",
        "",
        "Customer Details:",
        f"Name: {customer.get('name', '')}",
        f"Email: {customer.get('email', '')}",
        f"Phone: {customer.get('phone', '')}",
        f"Address: {delivery.get('address', '')}, {delivery.get('city', '')} - {delivery.get('pincode', '')}",
        "",
        "-----------------------------------------",
        "Items:",
        "-----------------------------------------",
        f"{'Product':<22}{'Qty':>5}{'Price':>10}{'Total':>10}",
    ]

    for item in items:
        name = str(item.get("name", ""))[:21]
        lines.append(
            f"{name:<22}{int(item.get('quantity', 0)):>5}"
            f"{_money(item.get('price', 0)):>10.2f}{_money(item.get('total', 0)):>10.2f}"
        )

    lines.extend(
        [
            "",
            "-----------------------------------------",
            f"Subtotal:       {_money(pricing.get('subtotal', 0)):.2f}",
            f"Tax (5%):       {_money(pricing.get('tax', 0)):.2f}",
            f"Delivery:       {_money(pricing.get('delivery_fee', 0)):.2f}",
            f"Discount:       {_money(pricing.get('discount', 0)):.2f}",
            "-----------------------------------------",
            f"Grand Total:    {_money(pricing.get('grand_total', 0)):.2f}",
            "-----------------------------------------",
            f"Payment Method: {payment.get('method', '')}",
            f"Payment Status: {payment.get('status', '')}",
            f"Order Status: {delivery.get('status', '')}",
            "-----------------------------------------",
        ]
    )
    return "\n".join(lines)


def checkout(
    user_id: int,
    db: Session,
    customer: dict[str, Any] | None = None,
    delivery: dict[str, Any] | None = None,
    payment_method: str = "COD",
    discount: float = DEFAULT_DISCOUNT,
) -> dict[str, Any]:
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
    if not cart_items:
        return {"action": "checkout", "error": "cart_empty"}

    product_map: dict[int, Product] = {}
    for item in cart_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            return {"action": "checkout", "error": "product_not_found", "product_id": item.product_id}
        if product.stock < item.quantity:
            return {
                "action": "checkout",
                "error": "out_of_stock",
                "product_id": product.id,
                "available": product.stock,
            }
        product_map[item.product_id] = product

    order_items: list[dict[str, Any]] = []
    subtotal = 0.0
    for item in cart_items:
        product = product_map[item.product_id]
        line_total = _money(product.price * item.quantity)
        subtotal += line_total
        order_items.append(
            {
                "product_id": product.id,
                "name": product.name,
                "price": _money(product.price),
                "quantity": int(item.quantity),
                "total": line_total,
            }
        )

    subtotal = _money(subtotal)
    tax = _money(subtotal * TAX_RATE)
    discount = _money(discount)
    grand_total = _money(subtotal + tax + DELIVERY_FEE - discount)
    user = db.query(User).filter(User.id == user_id).first()

    payment = {
        "method": payment_method.upper(),
        "status": "Pending" if payment_method.upper() == "COD" else "Paid",
    }
    delivery_info = _default_delivery(delivery)
    customer_info = _default_customer(user, customer)
    pricing = {
        "subtotal": subtotal,
        "tax": tax,
        "delivery_fee": _money(DELIVERY_FEE),
        "discount": discount,
        "grand_total": grand_total,
    }

    order = Order(
        user_id=user_id,
        total_amount=grand_total,
        status="Processing",
        customer=customer_info,
        items=order_items,
        pricing=pricing,
        payment=payment,
        delivery=delivery_info,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    order.order_id = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{order.id:06d}"
    created_at = order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat()
    order_payload = {
        "order_id": order.order_id,
        "created_at": created_at,
        "customer": customer_info,
        "items": order_items,
        "pricing": pricing,
        "payment": payment,
        "delivery": delivery_info,
    }
    order.invoice_text = generate_invoice(order_payload)

    for item in cart_items:
        product = product_map[item.product_id]
        product.stock -= item.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item.quantity,
                price=product.price,
            )
        )

    for item in cart_items:
        db.delete(item)

    db.commit()

    order_payload["invoice_text"] = order.invoice_text
    return {
        "action": "checkout",
        "user_id": user_id,
        "order_id": order.order_id,
        "id": order.id,
        "status": order.status,
        "total_amount": order.total_amount,
        "order": order_payload,
        "invoice_text": order.invoice_text,
    }
