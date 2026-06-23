from __future__ import annotations

from typing import Dict, List

from sqlalchemy import func, or_

from app.db.session import SessionLocal
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.embedding_service import generate_product_embedding, cosine_similarity


def _ensure_product_embeddings(db, products: list[Product]) -> None:
    changed = False
    for product in products:
        if product.embedding:
            continue
        embedding = generate_product_embedding(product)
        if not embedding:
            continue
        product.embedding = embedding
        changed = True

    if changed:
        db.commit()


def _average_embeddings(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None

    length = len(vectors[0])
    totals = [0.0] * length
    valid_count = 0

    for vec in vectors:
        if len(vec) != length:
            continue
        valid_count += 1
        for i, val in enumerate(vec):
            totals[i] += float(val)

    if valid_count == 0:
        return None
    return [v / valid_count for v in totals]


def _build_user_profile(db, user_id: int, held_out_product_id: int | None = None) -> dict:
    user_rows = (
        db.query(
            Product.category,
            Product.brand,
            OrderItem.price,
            func.sum(OrderItem.quantity).label("qty"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(Order.user_id == user_id)
        .filter(OrderItem.product_id != held_out_product_id if held_out_product_id is not None else True)
        .group_by(Product.category, Product.brand, OrderItem.price)
        .all()
    )

    category_counts: Dict[str, int] = {}
    brand_counts: Dict[str, int] = {}
    prices: List[float] = []

    for category, brand, price, qty in user_rows:
        q = int(qty or 0)
        if category:
            category_counts[category] = category_counts.get(category, 0) + q
        if brand:
            brand_counts[brand] = brand_counts.get(brand, 0) + q
        if price is not None:
            prices.append(float(price))

    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None

    purchased_product_ids = {
        pid
        for (pid,) in (
            db.query(OrderItem.product_id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Order.user_id == user_id)
            .filter(OrderItem.product_id != held_out_product_id if held_out_product_id is not None else True)
            .distinct()
            .all()
        )
    }

    purchased_products = (
        db.query(Product).filter(Product.id.in_(purchased_product_ids)).all() if purchased_product_ids else []
    )
    user_embedding = _average_embeddings([p.embedding for p in purchased_products if p.embedding])

    return {
        "category_counts": category_counts,
        "brand_counts": brand_counts,
        "min_price": min_price,
        "max_price": max_price,
        "purchased_product_ids": purchased_product_ids,
        "user_embedding": user_embedding,
    }


def _category_popularity(db) -> Dict[str, float]:
    rows = (
        db.query(Product.category, func.sum(OrderItem.quantity).label("qty"))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Product.category)
        .all()
    )

    counts = {category: int(qty or 0) for category, qty in rows if category}
    if not counts:
        return {}

    max_count = max(counts.values()) or 1
    return {category: count / max_count for category, count in counts.items()}


def _content_score(product: Product, profile: dict) -> float:
    category_counts = profile["category_counts"]
    brand_counts = profile["brand_counts"]

    score = 0.0

    if category_counts and product.category in category_counts:
        max_cat = max(category_counts.values()) or 1
        score += 0.5 * (category_counts[product.category] / max_cat)

    if brand_counts and product.brand and product.brand in brand_counts:
        max_brand = max(brand_counts.values()) or 1
        score += 0.3 * (brand_counts[product.brand] / max_brand)

    min_price = profile["min_price"]
    max_price = profile["max_price"]
    if min_price is not None and max_price is not None:
        p = float(product.price)
        if min_price <= p <= max_price:
            score += 0.2
        else:
            span = max(max_price - min_price, 1.0)
            dist = min(abs(p - min_price), abs(p - max_price))
            score += max(0.0, 0.2 * (1.0 - (dist / span)))

    return min(max(score, 0.0), 1.0)


def get_recommendations(
    user_id: int,
    limit: int = 5,
    held_out_product_id: int | None = None,
    mode: str = "semantic",
) -> list[dict]:
    db = SessionLocal()
    try:
        valid_modes = {"content", "hybrid", "semantic"}
        mode = mode if mode in valid_modes else "semantic"

        if mode == "semantic":
            all_products = db.query(Product).all()
            _ensure_product_embeddings(db, all_products)

        profile = _build_user_profile(db, user_id, held_out_product_id=held_out_product_id)
        popularity = _category_popularity(db)

        if held_out_product_id is not None:
            # Keep the held-out product eligible during evaluation even if stock reached 0.
            products = db.query(Product).filter(or_(Product.stock > 0, Product.id == held_out_product_id)).all()
        else:
            products = db.query(Product).filter(Product.stock > 0).all()

        # Do not globally exclude previously purchased items from recommendation candidates.
        candidates = products

        scored = []
        for product in candidates:
            embedding_similarity = cosine_similarity(profile["user_embedding"] or [], product.embedding or [])
            content_score = _content_score(product, profile)
            popularity_score = popularity.get(product.category, 0.0)
            if mode == "content":
                final_score = content_score
            elif mode == "hybrid":
                final_score = (0.6 * content_score) + (0.4 * popularity_score)
            else:
                final_score = (0.5 * embedding_similarity) + (0.3 * content_score) + (0.2 * popularity_score)
            scored.append(
                {
                    "product_id": str(product.id),
                    "name": product.name,
                    "score": float(round(final_score, 4)),
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
    finally:
        db.close()
