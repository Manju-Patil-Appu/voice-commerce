from __future__ import annotations

import os
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

from app.db.session import SessionLocal
from app.models.user import User
from app.services.evaluation_service import evaluate_user_with_mode


MODES = ["content", "hybrid", "semantic"]
K = 5


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def main() -> None:
    db = SessionLocal()
    try:
        user_ids = [u.id for u in db.query(User.id).all()]
    finally:
        db.close()

    print("Mode      Precision@5   Recall@5   HitRate@5   NDCG@5")
    print("------------------------------------------------------")

    for mode in MODES:
        precisions: list[float] = []
        recalls: list[float] = []
        hit_rates: list[float] = []
        ndcgs: list[float] = []

        for user_id in user_ids:
            result = evaluate_user_with_mode(user_id=user_id, mode=mode, k=K)
            precisions.append(float(result["precision"]))
            recalls.append(float(result["recall"]))
            hit_rates.append(float(result["hit_rate"]))
            ndcgs.append(float(result["ndcg"]))

        avg_precision = _avg(precisions)
        avg_recall = _avg(recalls)
        avg_hit_rate = _avg(hit_rates)
        avg_ndcg = _avg(ndcgs)

        print(
            f"{mode:<9} {avg_precision:>11.4f} {avg_recall:>10.4f} {avg_hit_rate:>11.4f} {avg_ndcg:>8.4f}"
        )


if __name__ == "__main__":
    main()
