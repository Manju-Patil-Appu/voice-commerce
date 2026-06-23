from __future__ import annotations

from threading import Lock
from typing import Iterable
import math

from sentence_transformers import SentenceTransformer


_MODEL: SentenceTransformer | None = None
_MODEL_LOCK = Lock()


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def generate_text_embedding(text: str) -> list[float]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    model = _get_model()
    vector = model.encode(cleaned)
    return [float(v) for v in vector.tolist()]


def generate_product_embedding(product) -> list[float]:
    parts = [product.name, product.category, product.brand, getattr(product, "description", None)]
    text = " ".join([p.strip() for p in parts if p and str(p).strip()])
    return generate_text_embedding(text)


def cosine_similarity(vec1: Iterable[float], vec2: Iterable[float]) -> float:
    a = [float(x) for x in vec1]
    b = [float(x) for x in vec2]
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
