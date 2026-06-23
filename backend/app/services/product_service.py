from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.product import Product


def _apply_product_filters(query, entities: dict):
    product_id_list = entities.get("product_id_list")
    name = entities.get("name")
    category = entities.get("category")
    brand = entities.get("brand")
    size = entities.get("size")
    color = entities.get("color")
    price_range = entities.get("price_range")

    if product_id_list:
        try:
            ids = [int(x) for x in product_id_list]
            query = query.filter(Product.id.in_(ids))
        except Exception:
            pass
    if name:
        name_value = str(name).strip().lower()
        brand_value = str(brand or "").strip().lower()
        generic_terms = {"shoe", "shoes", "sneaker", "sneakers", "footwear", "product"}
        if name_value == brand_value or name_value in generic_terms:
            name = None
    if name:
        query = query.filter(Product.name.ilike(f"%{name}%"))
    if category:
        query = query.filter(func.lower(Product.category) == str(category).strip().lower())
    if brand:
        query = query.filter(func.lower(Product.brand) == str(brand).strip().lower())
    if size:
        query = query.filter(Product.size == str(size))
    if color:
        query = query.filter(Product.color.ilike(f"%{color}%"))

    if price_range:
        min_price = None
        max_price = None
        pr = str(price_range).strip()
        if "-" in pr:
            parts = pr.split("-", 1)
            try:
                min_price = float(parts[0].strip())
                max_price = float(parts[1].strip())
            except ValueError:
                pass
        elif pr.startswith("<"):
            try:
                max_price = float(pr[1:].strip())
            except ValueError:
                pass
        elif pr.startswith(">"):
            try:
                min_price = float(pr[1:].strip())
            except ValueError:
                pass
        else:
            # treat single number as max price
            try:
                max_price = float(pr)
            except ValueError:
                pass

        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

    return query


def search_products(db: Session, entities: dict) -> dict[str, Any]:
    query = db.query(Product)
    query = _apply_product_filters(query, entities)
    products = query.all()

    items = [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "brand": p.brand,
            "size": p.size,
            "color": p.color,
            "description": p.description,
            "price": p.price,
            "stock": p.stock,
            "images": p.images or [],
        }
        for p in products
    ]

    return {"action": "search_product", "filters": entities, "items": items}


def find_first_product(db: Session, entities: dict) -> Product | None:
    query = db.query(Product)
    query = _apply_product_filters(query, entities)
    return query.first()
