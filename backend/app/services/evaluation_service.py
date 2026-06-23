from __future__ import annotations

import math

from app.db.session import SessionLocal
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.recommendation_service import get_recommendations


def precision_at_k(recommended_ids, relevant_ids, k):
    if k <= 0:
        return 0.0
    top_k = list(recommended_ids)[:k]
    relevant = set(relevant_ids)
    hits = sum(1 for pid in top_k if pid in relevant)
    return hits / float(k)


def recall_at_k(recommended_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    if k <= 0 or not relevant:
        return 0.0
    top_k = list(recommended_ids)[:k]
    hits = sum(1 for pid in top_k if pid in relevant)
    return hits / float(len(relevant))


def hit_rate_at_k(recommended_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    if k <= 0 or not relevant:
        return 0.0
    top_k = list(recommended_ids)[:k]
    return 1.0 if any(pid in relevant for pid in top_k) else 0.0


def ndcg_at_k(recommended_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    if k <= 0 or not relevant:
        return 0.0

    top_k = list(recommended_ids)[:k]
    dcg = 0.0
    for i, pid in enumerate(top_k):
        rel = 1.0 if pid in relevant else 0.0
        if rel > 0.0:
            dcg += rel / math.log2(i + 2)

    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0

    idcg = 0.0
    for i in range(ideal_hits):
        idcg += 1.0 / math.log2(i + 2)

    return dcg / idcg if idcg > 0.0 else 0.0


def evaluate_user(user_id: int, k: int = 5):
    db = SessionLocal()
    try:
        last_purchase = (
            db.query(OrderItem.product_id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Order.user_id == user_id)
            .order_by(Order.id.desc(), OrderItem.id.desc())
            .first()
        )

        if not last_purchase:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "hit_rate": 0.0,
                "ndcg": 0.0,
            }

        hidden_product_id = int(last_purchase[0])
        recs = get_recommendations(user_id=user_id, limit=k, held_out_product_id=hidden_product_id)
        recommended_ids = [int(r["product_id"]) for r in recs]
        relevant_ids = [hidden_product_id]

        return {
            "precision": float(precision_at_k(recommended_ids, relevant_ids, k)),
            "recall": float(recall_at_k(recommended_ids, relevant_ids, k)),
            "hit_rate": float(hit_rate_at_k(recommended_ids, relevant_ids, k)),
            "ndcg": float(ndcg_at_k(recommended_ids, relevant_ids, k)),
        }
    finally:
        db.close()


def evaluate_user_with_mode(user_id: int, mode: str, k: int = 5):
    db = SessionLocal()
    try:
        last_purchase = (
            db.query(OrderItem.product_id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Order.user_id == user_id)
            .order_by(Order.id.desc(), OrderItem.id.desc())
            .first()
        )

        if not last_purchase:
            return {
                "mode": mode,
                "precision": 0.0,
                "recall": 0.0,
                "hit_rate": 0.0,
                "ndcg": 0.0,
            }

        hidden_product_id = int(last_purchase[0])
        recs = get_recommendations(
            user_id=user_id,
            limit=k,
            held_out_product_id=hidden_product_id,
            mode=mode,
        )
        recommended_ids = [int(r["product_id"]) for r in recs]
        relevant_ids = [hidden_product_id]

        return {
            "mode": mode,
            "precision": float(precision_at_k(recommended_ids, relevant_ids, k)),
            "recall": float(recall_at_k(recommended_ids, relevant_ids, k)),
            "hit_rate": float(hit_rate_at_k(recommended_ids, relevant_ids, k)),
            "ndcg": float(ndcg_at_k(recommended_ids, relevant_ids, k)),
        }
    finally:
        db.close()
