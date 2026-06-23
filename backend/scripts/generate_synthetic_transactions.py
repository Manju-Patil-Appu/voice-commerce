from __future__ import annotations

import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.example")

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:password@localhost:5432/ecommerce"
if not os.getenv("JWT_SECRET"):
    os.environ["JWT_SECRET"] = "change-me"

from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User


NUM_USERS = 500
MIN_ORDERS_PER_USER = 3
MAX_ORDERS_PER_USER = 10


PRICE_RANGES = {
    "Budget": (999, 1999),
    "Mid": (2000, 4999),
    "Premium": (5000, 9999),
}


def _desc_tokens(product: Product) -> set[str]:
    text = (product.description or "").lower()
    tokens = {t for t in text.replace("\n", " ").split(" ") if len(t) > 3}
    return tokens


def _price_in_range(price: float, pref_range: str) -> bool:
    low, high = PRICE_RANGES[pref_range]
    return low <= float(price) <= high


def _pick_product(
    products: list[Product],
    preferred_category: str,
    preferred_brand: str,
    preferred_size: str,
    preferred_price_range: str,
    excluded_product_ids: set[int],
) -> Product | None:
    available = [p for p in products if p.stock > 0 and p.id not in excluded_product_ids]
    if not available:
        return None

    # 15% random exploration purchases.
    if random.random() < 0.15:
        return random.choice(available)

    # 25% semantically similar pick using description keyword overlap.
    if random.random() < 0.25:
        seed_pool = [p for p in available if p.category == preferred_category] or available
        seed = random.choice(seed_pool)
        seed_tokens = _desc_tokens(seed)
        if seed_tokens:
            ranked = sorted(
                available,
                key=lambda p: len(seed_tokens.intersection(_desc_tokens(p))),
                reverse=True,
            )
            if ranked:
                return ranked[0]

    target_category = preferred_category if random.random() < 0.55 else None
    target_brand = preferred_brand if random.random() < 0.45 else None
    target_size = preferred_size if random.random() < 0.65 else None
    target_price = preferred_price_range if random.random() < 0.70 else None

    candidates = available
    if target_category is not None:
        candidates = [p for p in candidates if p.category == target_category]
    if target_brand is not None and candidates:
        filtered = [p for p in candidates if p.brand == target_brand]
        candidates = filtered if filtered else candidates
    if target_size is not None and candidates:
        filtered = [p for p in candidates if p.size == target_size]
        candidates = filtered if filtered else candidates
    if target_price is not None and candidates:
        filtered = [p for p in candidates if _price_in_range(p.price, target_price)]
        candidates = filtered if filtered else candidates

    if not candidates:
        return None
    return random.choice(candidates)


def main() -> None:
    random.seed(123)
    db = SessionLocal()

    users_created = 0
    total_orders = 0
    total_order_items = 0

    try:
        products = db.query(Product).all()
        if not products:
            print("Total users created: 0")
            print("Total orders: 0")
            print("Total order items: 0")
            return

        categories = sorted({p.category for p in products if p.category})
        brands = sorted({p.brand for p in products if p.brand})
        sizes = sorted({p.size for p in products if p.size})
        price_ranges = list(PRICE_RANGES.keys())

        max_user_id = db.query(func.max(User.id)).scalar() or 0

        for i in range(NUM_USERS):
            synthetic_idx = max_user_id + i + 1
            user = User(
                email=f"synthetic_user_{synthetic_idx}@example.com",
                password_hash="synthetic_password_hash",
            )
            db.add(user)
            db.flush()
            users_created += 1

            preferred_category = random.choice(categories)
            preferred_brand = random.choice(brands)
            preferred_size = random.choice(sizes)
            preferred_price_range = random.choice(price_ranges)

            order_count = random.randint(MIN_ORDERS_PER_USER, MAX_ORDERS_PER_USER)
            for _ in range(order_count):
                num_items = random.randint(1, 3)
                selected_lines: list[tuple[Product, int]] = []
                selected_product_ids: set[int] = set()

                for _ in range(num_items):
                    product = _pick_product(
                        products=products,
                        preferred_category=preferred_category,
                        preferred_brand=preferred_brand,
                        preferred_size=preferred_size,
                        preferred_price_range=preferred_price_range,
                        excluded_product_ids=selected_product_ids,
                    )
                    if product is None:
                        continue

                    quantity = random.randint(1, 2)
                    if product.stock < quantity:
                        continue

                    selected_lines.append((product, quantity))
                    selected_product_ids.add(product.id)

                if not selected_lines:
                    continue

                order = Order(user_id=user.id, total_amount=0.0, status="confirmed")
                db.add(order)
                db.flush()

                total_amount = 0.0
                for product, quantity in selected_lines:
                    product.stock -= quantity
                    line_price = float(product.price)
                    total_amount += line_price * quantity
                    db.add(
                        OrderItem(
                            order_id=order.id,
                            product_id=product.id,
                            quantity=quantity,
                            price=line_price,
                        )
                    )
                    total_order_items += 1

                order.total_amount = total_amount
                total_orders += 1

            if (i + 1) % 50 == 0:
                db.commit()

        db.commit()

        print(f"Total users created: {users_created}")
        print(f"Total orders: {total_orders}")
        print(f"Total order items: {total_order_items}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
