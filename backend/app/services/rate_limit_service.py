from collections import defaultdict, deque
from time import time

from fastapi import HTTPException, Request

from app.core.config import settings


_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit_key(request: Request, action: str, email: str | None = None) -> str:
    normalized_email = str(email).lower() if email else ""
    return f"{action}:{_client_ip(request)}:{normalized_email}"


def check_rate_limit(key: str, limit: int, window_seconds: int | None = None) -> None:
    now = time()
    window = window_seconds or settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    attempts = _ATTEMPTS[key]

    while attempts and now - attempts[0] >= window:
        attempts.popleft()

    if len(attempts) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    attempts.append(now)
